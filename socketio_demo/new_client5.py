import streamlit as st
import socketio
import sounddevice as sd
import numpy as np
import requests
import os
from playsound import playsound

# Create a Socket.IO client
sio = socketio.Client()

# Audio recording settings
SAMPLE_RATE = 16000  # Hz
CHUNK_SIZE = 1024  # Number of samples per chunk
CHANNELS = 1  # Mono audio
stream=None

class SessionState:
    def __init__(self):
        self.transcription = None
        self.answer = None
        self.download_url = None
        self.rerun=False
session_state=SessionState()
def callback(indata, frames, time, status):
    """Capture audio and send it to the server."""
    if status:
        print(f"Error: {status}")
    audio_chunk = (indata * 32767).astype(np.int16)
    sio.emit("audio_chunk", audio_chunk.tobytes())

def stop_streaming():
    """Stop recording and streaming audio."""
    global stream
    if stream is not None:
        stream.stop()
        stream.close()
        stream = None

def start_streaming():
    """Start recording and streaming audio."""
    global stream
    if stream is None:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=callback,
            blocksize=CHUNK_SIZE
        )
        stream.start()
        print("🎤 Recording started...")

@sio.event
def connect():
    print("✅ Connected to server")
    start_streaming()

@sio.event
def disconnect():
    print("❌ Disconnected from server")
    stop_streaming()
@sio.event
def processing_started():
    """Server has started processing the audio"""
    global is_processing
    is_processing = True
    stop_streaming()

def processing_complete():
    """Server has finished processing the audio"""
    global is_processing
    is_processing = False
    stop_streaming()
    start_streaming()

@sio.event
def processing_error():
    """Server encountered an error during processing"""
    global is_processing
    is_processing = False
    stop_streaming()
    start_streaming()
@sio.event
def transcription_received(text):
    """Receive transcription from the server."""
    session_state.transcription=text
    session_state.rerun=True
    print("rerun set")

@sio.event
def answer_received(answer):
    """Receive assistant answer from the server."""
    session_state.answer=answer
    session_state.rerun=True
    print("rerun set")

@sio.event
def download_url_received(url):
    """Receive audio download URL from the server."""
    session_state.download_url=url
    session_state.rerun=True
    print("rerun set")

def main():
    st.title("Real-Time Audio Streaming")

    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    
    if uploaded_file is not None:
        st.write("File uploaded successfully!")
        if st.button("Send to API"):
            API_URL = "http://127.0.0.1:8001/upload"
            files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
            response = requests.post(API_URL, files=files)

            if response.status_code == 200:
                st.write("File has been sent to the server API!")
                
            else:
                st.write(f"Failed to send the file. Status code: {response.status_code}")
                st.write("Error: ", response.text)

    if st.button("Start Streaming"):
        sio.connect("http://localhost:5000")

    # Display transcription and assistant answer
    if session_state.transcription:
        st.write(f"👤 **You:** {session_state.transcription}")
        session_state.transcription = None

    if session_state.answer:
        st.write(f"🤖 **Assistant:** {session_state.answer}")
        session_state.answer = None

    # Handle audio playback
    if session_state.download_url:
        file_name = os.path.basename(session_state.download_url)
        audio_response = requests.get(session_state.download_url)
        if audio_response.status_code == 200:
            with open(file_name, "wb") as file:
                file.write(audio_response.content)
            playsound(file_name)  # Play the received audio
            processing_complete()
        session_state.download_url = None  # Clear URL after playing
    
    if session_state.rerun:
        print("rerunning")
        session_state.rerun = False  # Reset the flag
        st.rerun()  # Rerun the Streamlit app
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.write(f"Error: {e}")