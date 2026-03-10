import sounddevice as sd
from faster_whisper import WhisperModel
import queue
import logging
import threading


from ai_Cleanup import refine

logger = logging.getLogger(__name__)

# Sentinel object to signal end of transcription queue
_TRANSCRIPTION_STOP_SIGNAL = object()


class WhisperWorker(threading.Thread):
    """Dedicated worker thread for Whisper transcription"""
    def __init__(self, model, transcription_queue, text_callback):
        super().__init__(daemon=True, name="WhisperWorkerThread")
        self.model = model
        self.transcription_queue = transcription_queue
        self.text_callback = text_callback
        self.chunk_processed_count = 0
        
    def run(self):
        logger.info(f"WhisperWorkerThread started | Listening for audio chunks")
        try:
            while True:
                # Get next audio chunk with timeout
                try:
                    audio = self.transcription_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Check for stop signal
                if audio is _TRANSCRIPTION_STOP_SIGNAL:
                    logger.info("WhisperWorkerThread received stop signal")
                    break
                
                # Process audio with Whisper
                self.chunk_processed_count += 1
                logger.debug(f"WhisperWorker processing chunk #{self.chunk_processed_count} | Queue depth: {self.transcription_queue.qsize()}")
                
                try:
                    lines, _ = self.model.transcribe(
                        audio,
                        language="en",
                        vad_filter=True
                    )
                    lines = list(lines)
                    logger.debug(f"Whisper transcription completed | Lines: {len(lines)} | Queue depth: {self.transcription_queue.qsize()}")
                    
                    for line in lines:
                        text = line.text.strip()
                        if text:
                            logger.info(f"[WhisperWorker] Transcribed: '{text}'")
                            self.text_callback(text)
                        else:
                            logger.debug("Whisper returned empty text")
                            
                except Exception as e:
                    logger.error(f"Error in WhisperWorker transcription: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Fatal error in WhisperWorkerThread: {e}", exc_info=True)
        finally:
            logger.info(f"WhisperWorkerThread exited | Total chunks processed: {self.chunk_processed_count}")


class LiveSpeechRecorder:
    def __init__(self):
        self.SAMPLE_RATE = 16000 # Hz
        self.CHUNK_DURATION = 3 # seconds
        self.BLOCKSIZE = int(self.SAMPLE_RATE * self.CHUNK_DURATION) # audio samples per chunk
        self.BLOCK_WORD_LIMIT = 30 # max words per block
        self.buffer_block = "" # current text buffer
        self.saved_block = [] # saved text for final cleanup
        self.text_on = None # live text callback
        logger.info("LiveSpeechRecorder initialized")

        self.model = WhisperModel(
            "small",
            compute_type="int8"
        )
        logger.info("Whisper model loaded")

        self.audio_queue = queue.Queue() # Audio chunks from mic (producer: audio callback)
        self.transcription_queue = queue.Queue() # Audio chunks awaiting Whisper transcription
        self.whisper_worker = None # WhisperWorker thread
        self.stream = None # audio stream
        self.is_recording = False
        self.audio_chunk_count = 0

    def show_text(self, text):
        """Callback to handle transcribed text - updates buffer and sends to UI"""
        if self.text_on:
            logger.debug(f"show_text() callback invoked with: '{text}'")
            self.buffer_block += " " + text # store for cleanup
            logger.debug(f"Buffer updated | Current size: {len(self.buffer_block.split())} words")

            # save block once it gets long enough
            if len(self.buffer_block.split()) >= self.BLOCK_WORD_LIMIT:
                self.saved_block.append(self.buffer_block.strip())
                logger.info(f"Block saved | Total blocks: {len(self.saved_block)} | Block size: {len(self.buffer_block.split())} words")
                self.buffer_block = ""
            
            self.text_on(text)  # Send to UI queue
        else:
            logger.warning("show_text() called but no callback registered")
            

    def audio_callback(self, indata, frames, time, status):
        """Callback from audio stream - enqueues audio for transcription"""
        if status:
            logger.warning(f"Audio callback status: {status}")
        self.audio_chunk_count += 1
        audio_data = indata.copy()
        self.audio_queue.put(audio_data)  # push to audio queue for fast dequeue
        logger.debug(f"Audio chunk #{self.audio_chunk_count} enqueued | Audio queue size: {self.audio_queue.qsize()} | Shape: {audio_data.shape}")


    def start_recording(self):
        logger.info(f"start_recording() called in thread: {threading.current_thread().name}")
        self.is_recording = True
        self.audio_chunk_count = 0

        # Start WhisperWorker thread for transcription
        self.whisper_worker = WhisperWorker(self.model, self.transcription_queue, self.show_text)
        logger.info("Starting WhisperWorkerThread")
        self.whisper_worker.start()
        logger.info(f"WhisperWorkerThread started. Active threads: {threading.active_count()}")

        # open mic stream
        self.stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=1,
            blocksize=self.BLOCKSIZE,
            dtype="float32",
            callback=self.audio_callback
        )
        logger.info(f"Audio stream created | Sample rate: {self.SAMPLE_RATE}Hz | Blocksize: {self.BLOCKSIZE}")

        self.stream.start()
        logger.info("Audio stream started - listening for input")

        try:
            while self.is_recording:
                # Dequeue audio chunk - moves data fast
                audio = self.audio_queue.get().flatten()
                logger.debug(f"Audio chunk dequeued from audio_queue | Remaining: {self.audio_queue.qsize()} | Transcription queue depth: {self.transcription_queue.qsize()} | Audio shape: {audio.shape}")
                
                # Enqueue for transcription - non-blocking
                self.transcription_queue.put(audio)
                logger.debug(f"Audio chunk enqueued to transcription_queue | Depth: {self.transcription_queue.qsize()}")

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt detected in start_recording()")
            self.stop_recording()
        except Exception as e:
            logger.error(f"Exception in start_recording: {e}", exc_info=True)
        finally:
            logger.info(f"start_recording() loop exited. Total chunks dequeued and forwarded: {self.audio_chunk_count}")


    def stop_recording(self):
        logger.info(f"stop_recording() called in thread: {threading.current_thread().name}")
        self.is_recording = False
        logger.info("Recording flag set to False")

        if self.stream:
            self.stream.stop()
            self.stream.close()
            logger.info("Audio stream stopped and closed")
        
        logger.info(f"Audio queue remaining items: {self.audio_queue.qsize()}")
        logger.info(f"Transcription queue remaining items: {self.transcription_queue.qsize()}")
        
        # Drain remaining audio from audio_queue to transcription_queue before stopping worker
        remaining_count = 0
        while not self.audio_queue.empty():
            try:
                audio = self.audio_queue.get_nowait().flatten()
                self.transcription_queue.put(audio)
                remaining_count += 1
                logger.info(f"Drained audio chunk #{self.audio_chunk_count - remaining_count + 1} to transcription_queue")
            except queue.Empty:
                break
        
        if remaining_count > 0:
            logger.info(f"Drained {remaining_count} remaining audio chunks from audio_queue")
        
        # Signal WhisperWorker to stop after processing all enqueued audio
        logger.info("Sending stop signal to WhisperWorkerThread")
        self.transcription_queue.put(_TRANSCRIPTION_STOP_SIGNAL)
        
        # Wait for WhisperWorker to finish
        if self.whisper_worker:
            logger.info("Waiting for WhisperWorkerThread to complete")
            self.whisper_worker.join(timeout=120)  # Wait up to 2 minutes
            if self.whisper_worker.is_alive():
                logger.warning("WhisperWorkerThread did not complete within timeout")
            else:
                logger.info("WhisperWorkerThread completed successfully")
        
        # save leftover text
        if self.buffer_block.strip():
            self.saved_block.append(self.buffer_block.strip())
            logger.info(f"Leftover buffer saved | Total blocks now: {len(self.saved_block)} | Leftover size: {len(self.buffer_block.split())} words")
        
        logger.info(f"Total blocks to cleanup: {len(self.saved_block)} blocks")
        for i, block in enumerate(self.saved_block):
            logger.debug(f"Block {i+1}: {len(block.split())} words - {block[:50]}...")
        
        logger.info("Calling refine() to process blocks with AI cleanup")
        cleaned_notes = refine(self.saved_block)
        logger.info(f"AI cleanup completed | Result size: {len(cleaned_notes)} characters")
        return cleaned_notes
    