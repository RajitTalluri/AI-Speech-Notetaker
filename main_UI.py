import tkinter as tk
from tkinter import ttk
import threading
import queue

from Audio_to_Speech import LiveSpeechRecorder


class SpeechNotetakerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Speech Notetaker")
        self.root.geometry("800x600")

        self.recorder = LiveSpeechRecorder()
        self.recording_thread = None
        self.ui_queue = queue.Queue()
        self.process_ui_queue()
        self.make_buttons()


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

        ttk.Label(self.root, text="Live Speech").pack()
        self.live_text = tk.Text(self.root, height=10)
        self.live_text.pack(fill=tk.BOTH, padx=10, pady=5)

        ttk.Label(self.root, text="Cleaned Notes").pack()
        self.notes_text = tk.Text(self.root, height=15)
        self.notes_text.pack(fill=tk.BOTH, padx=10, pady=5)


    def start_recording(self):
        self.live_text.delete("1.0", tk.END)
        self.notes_text.delete("1.0", tk.END)

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.recorder.text_on = self.enqueue_live_text

        self.recording_thread = threading.Thread(
            target=self.record_audio,
            daemon=True
        )
        self.recording_thread.start()

    def record_audio(self):
        self.recorder.start_recording()


    def enqueue_live_text(self, text):
        self.ui_queue.put(text)


    def process_ui_queue(self):
        while not self.ui_queue.empty():
            text = self.ui_queue.get()
            self.live_text.insert(tk.END, text + "\n")
            self.live_text.see(tk.END)
        self.root.after(100, self.process_ui_queue)
    
    
    def stop_recording(self):
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

        notes = self.recorder.stop_recording()
        self.notes_text.insert(tk.END, notes)



if __name__ == "__main__":
    root = tk.Tk()
    app = SpeechNotetakerUI(root)
    root.mainloop()




# C:\Users\rajit\AppData\Local\Programs\Python\Python311\python.exe "c:/Speech Notetaker/main_UI.py"