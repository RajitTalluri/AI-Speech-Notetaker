# Real-Time Speech Notetaker

## Overview
A real time speech-to-text notetaker for workflows where hands-on work makes traditional note taking difficult.

The goal is tp have low latency transcription and produce accurate, structured notes at the end of a session.

## System Architecture
Refer to **Speech Notetaker Outline.svg** for the diagram.

A multi-threaded design is used to avoid UI freezing and to ensure audio is captured continuously without missing data.

### Threading Model
- **Main Thread (Tkinter UI)**
  Displays nearly real time transcription and handles user interaction.

- **Thread 1 (Audio Capture)**  
  Continuously records audio and pushes fixed-length chunks into a queue to minimize latency and prevent dropped speech.

- **Thread 2 (Transcription)**  
  Uses OpenAI Whisper to convert queued audio chunks into text.

## Transcription Pipeline
- Audio is processed in 3-second chunks, providing enough context for accurate Whisper transcription while keeping updates nearly live.
- Recording sessions can be paused and resumed without losing context.
- When recording is stopped, the transcription is sent to Ollama phi-3 on the local machine.
- A custom prompt cleans and formats the transcription into structured notes.
- If recording is resumed, new speech is appended to the existing transcription and included in the final note-cleaning step.

## Design Decisions
- Used multi-threading to prevent Tkinter from freezing during real time updates.
- Continuous audio capture reduces latency and avoids missed speech.
- Local LLM inference keeps the system free and useable offline.
- Appending transcriptions across recording breaks preserves context for greaer quality note formatting.

## Future Improvements
- Make system completely hands free by using voice-based start and stop activation.
- Use of a larger or more capable language model for better quality refined notes.
- Allow for specific context realted to the user's topic for more accurate and insightful note refinement.
