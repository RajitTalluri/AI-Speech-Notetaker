import tkinter as tk
from tkinter import ttk
import threading
import queue
from tkinter import filedialog, messagebox
import logging
from datetime import datetime
import signal
import sys
import os

from Audio_to_Speech import LiveSpeechRecorder

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(threadName)-12s] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('speech_notetaker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SpeechNotetakerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Speech Notetaker")
        self.root.geometry("800x600")
        logger.info("=" * 60)
        logger.info("SpeechNotetakerUI initialized")

        self.recorder = LiveSpeechRecorder()
        self.recording_thread = None
        self.transcription_thread = None
        self.ui_queue = queue.Queue()
        self.full_transcript = ""
        self.is_shutting_down = False

        # Set up graceful shutdown handlers
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        signal.signal(signal.SIGINT, self.on_ctrl_c)

        self.process_ui_queue()
        self.make_buttons()
        
        logger.info(f"SpeechNotetakerUI ready. PID: {os.getpid()}")



    def make_buttons(self):
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=10)

        self.start_btn = ttk.Button(
            button_frame,
            text="Start Recording",
            command=self.start_recording
        )
        
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = ttk.Button(
            button_frame,
            text="Stop Recording",
            command=self.stop_recording,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT)
        
        self.save_btn = ttk.Button(
        button_frame,
        text="Save Notes",
        command=self.save_notes
        )
        self.save_btn.pack(side=tk.LEFT, padx=10)
        self.save_btn.config(state=tk.DISABLED)


        ttk.Label(self.root, text="Live Speech").pack()
        self.live_text = tk.Text(self.root, height=10)
        self.live_text.pack(fill=tk.BOTH, padx=10, pady=5)

        ttk.Label(self.root, text="Cleaned Notes").pack()
        self.notes_text = tk.Text(self.root, height=15)
        self.notes_text.pack(fill=tk.BOTH, padx=10, pady=5)
        
        self.status_label = ttk.Label(
        self.root,
        text="Idle",
        foreground="gray"
        )
        self.status_label.pack(pady=5)


    def start_recording(self):
        logger.info("START RECORDING button clicked")
        self.start_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        self.status_label.config(
        text="Recording... Speak Into Microphone",
        foreground="green"
        )
        
        self.recorder.text_on = self.enqueue_live_text

        self.recording_thread = threading.Thread(
            target=self.record_audio,
            daemon=True,
            name="RecordingThread"
        )
        logger.info(f"Starting recording thread: {self.recording_thread.name}")
        self.recording_thread.start()
        logger.info(f"Recording thread started. Active threads: {threading.active_count()}")

    def record_audio(self):
        logger.info("record_audio() executing in recording thread")
        try:
            self.recorder.start_recording()
        except Exception as e:
            logger.error(f"Error in record_audio: {e}", exc_info=True)
        finally:
            logger.info("record_audio() completed")


    def enqueue_live_text(self, text):
        self.ui_queue.put(text)
        logger.debug(f"Text enqueued to UI queue: '{text}' | Queue size: {self.ui_queue.qsize()}")


    def process_ui_queue(self):
        processed_count = 0
        while not self.ui_queue.empty():
            text = self.ui_queue.get()
            self.full_transcript += text + " " # include previous text
            self.live_text.insert(tk.END, text + "\n")
            self.live_text.see(tk.END)
            processed_count += 1
            logger.debug(f"Text processed from queue: '{text}' | Remaining in queue: {self.ui_queue.qsize()}")
        
        if processed_count > 0:
            logger.debug(f"Processed {processed_count} text items from UI queue")
        
        if not self.is_shutting_down:
            self.process_ui_queue_id = self.root.after(100, self.process_ui_queue)
    
    
    def stop_recording(self):
        logger.info("STOP RECORDING button clicked")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)

        self.status_label.config(
            text="Recording stopped. Processing ...",
            foreground="orange"
        )
        self.root.update_idletasks()
        logger.info(f"Full transcript collected so far: {len(self.full_transcript)} characters")

        self.transcription_thread = threading.Thread(
            target=self.finish_transcription,
            daemon=True,
            name="TranscriptionThread"
        )
        logger.info(f"Starting transcription thread: {self.transcription_thread.name}")
        self.transcription_thread.start()
        logger.info(f"Transcription thread started. Active threads: {threading.active_count()}")
        



    def save_notes(self):
        content = self.notes_text.get("1.0", tk.END).strip()

        if not content:
            messagebox.showwarning("Error", "No notes available to save.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")],
            title="Save Notes"
            )
        if not file_path:
            return  # cancelled by user

        try:
            with open(file_path, "w", encoding="utf-8") as fsave:
                fsave.write(content)
            messagebox.showinfo("Saved", f"Notes saved to {file_path}.")
                
        except Exception:
            messagebox.showerror("Error", f"Failed to save file:\n{Exception}")


    def finish_transcription(self):
        logger.info("finish_transcription() executing in transcription thread")
        try:
            logger.info("Calling recorder.stop_recording() to process audio blocks and cleanup")
            cleaned_notes = self.recorder.stop_recording()
            logger.info(f"Cleaned notes received: {len(cleaned_notes)} characters")
            self.root.after(0, lambda: self.on_transcription_done(cleaned_notes)) # result to UI thread
        except Exception as e:
            logger.error(f"Error in finish_transcription: {e}", exc_info=True)
        finally:
            logger.info("finish_transcription() completed")


    def on_transcription_done(self, notes):
        logger.info("on_transcription_done() executing on UI thread to display cleaned notes")
        self.notes_text.insert(tk.END, notes + "\n")
        self.status_label.config(
            text="Finished!",
            foreground="green"
        )
        logger.info(f"Cleaned notes displayed in UI: {len(notes)} characters")
        self.start_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)


    def on_window_close(self):
        """Handle window close event (X button)"""
        logger.info("=" * 60)
        logger.info("Window close event detected (X button clicked)")
        self.shutdown()


    def on_ctrl_c(self, signum, frame):
        """Handle Ctrl+C signal"""
        logger.info("=" * 60)
        logger.info("SIGINT received (Ctrl+C pressed)")
        self.shutdown()


    def shutdown(self):
        """Gracefully shutdown all threads and cleanup resources"""
        if self.is_shutting_down:
            logger.warning("Shutdown already in progress, ignoring duplicate shutdown request")
            return
        
        self.is_shutting_down = True
        logger.info("Starting graceful shutdown sequence...")
        logger.info(f"Active threads at shutdown: {threading.active_count()}")
        for thread in threading.enumerate():
            logger.debug(f"  - {thread.name} (daemon={thread.daemon})")
        
        # Step 1: Stop recording if active
        if self.recording_thread and self.recording_thread.is_alive():
            logger.info("Recording thread is active, stopping recording...")
            try:
                self.recorder.is_recording = False
                logger.info("Set is_recording=False, waiting for RecordingThread to exit...")
                self.recording_thread.join(timeout=5)
                if self.recording_thread.is_alive():
                    logger.warning("RecordingThread did not exit within 5 seconds")
                else:
                    logger.info("RecordingThread exited successfully")
            except Exception as e:
                logger.error(f"Error stopping recording thread: {e}", exc_info=True)
        
        # Step 2: Wait for transcription if active
        if self.transcription_thread and self.transcription_thread.is_alive():
            logger.info("Transcription thread is active, waiting for completion...")
            try:
                self.transcription_thread.join(timeout=60)
                if self.transcription_thread.is_alive():
                    logger.warning("TranscriptionThread did not exit within 60 seconds")
                else:
                    logger.info("TranscriptionThread exited successfully")
            except Exception as e:
                logger.error(f"Error waiting for transcription thread: {e}", exc_info=True)
        
        # Step 3: Stop UI queue processing
        logger.info("Stopping UI queue processing...")
        try:
            self.root.after_cancel(self.process_ui_queue_id) if hasattr(self, 'process_ui_queue_id') else None
            logger.info("UI queue processing stopped")
        except Exception as e:
            logger.debug(f"Could not cancel process_ui_queue: {e}")
        
        # Step 4: Final log and cleanup
        logger.info("Cleanup complete")
        logger.info(f"Active threads remaining: {threading.active_count()}")
        for thread in threading.enumerate():
            logger.debug(f"  - {thread.name} (daemon={thread.daemon})")
        
        logger.info("=" * 60)
        logger.info("Application shutdown complete")
        logger.info("=" * 60)
        
        # Destroy the window to exit mainloop
        try:
            self.root.destroy()
        except Exception as e:
            logger.error(f"Error destroying window: {e}")
        
        # Exit the application
        sys.exit(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = SpeechNotetakerUI(root)
    root.mainloop()




# C:\Users\rajit\AppData\Local\Programs\Python\Python311\python.exe "c:/Speech Notetaker/main_UI.py"