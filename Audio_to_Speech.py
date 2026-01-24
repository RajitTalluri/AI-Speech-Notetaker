import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import queue

from ai_Cleanup import refine


class LiveSpeechRecorder:
    def __init__(self):
        self.SAMPLE_RATE = 16000 # Hz
        self.CHUNK_DURATION = 3 # seconds
        self.BLOCKSIZE = int(self.SAMPLE_RATE * self.CHUNK_DURATION) # audio samples per chunk
        self.BLOCK_WORD_LIMIT = 30 # max words per block
        self.buffer_block = "" # current text buffer
        self.saved_block = [] # saved text for final cleanup
        self.text_on = None # live text callback

        self.model = WhisperModel(
            "small",
            compute_type="int8"
        )


        self.audio_queue = queue.Queue() # store audio chunks (latency) 
        self.stream = None # audio stream
        self.is_recording = False

    def show_text(self, text):
        if self.text_on:
            self.text_on(text)
            

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(status)  # check for audio issues
        self.audio_queue.put(indata.copy())  # push audio to queue


    def start_recording(self):
        print("Speak to mic (click stop to finish)")
        self.is_recording = True

        # open mic stream
        self.stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=1,
            blocksize=self.BLOCKSIZE,
            dtype="float32",
            callback=self.audio_callback
        )

        self.stream.start()

        try:
            while self.is_recording:
                audio = self.audio_queue.get().flatten()
                self.process_audio(audio)

        except KeyboardInterrupt:
            self.stop_recording()


    def process_audio(self, audio): # processes each audio chunk
        lines, _ = self.model.transcribe(
            audio,
            language="en",
            vad_filter=True # removes silence from transcription
        )

        for line in lines:
            text = line.text.strip() # cleans spacing
            if not text:
                continue

            self.show_text(text) # live speech output

            self.buffer_block += " " + text # store for cleanup

            # save block once it gets long enough
            if len(self.buffer_block.split()) >= self.BLOCK_WORD_LIMIT:
                self.saved_block.append(self.buffer_block.strip())
                print("\n Block Saved \n") # debug
                self.buffer_block = ""


    def stop_recording(self):
        print("\nStopped Recording.")
        self.is_recording = False

        if self.stream:
            self.stream.stop()
            self.stream.close()

        # save leftover text
        if self.buffer_block.strip():
            self.saved_block.append(self.buffer_block.strip())

        print("\n Cleaned Notes \n")
        return refine(self.saved_block)
