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

# Add state tracking
is_processing = False
stream = None
transcription_text = ""
assistant_answer = ""
download_url=""
temp="temp_output"
class SessionState:
    def __init__(self):
        self.transcription = None
        self.answer = None
        self.download_url = None
        self.connected = False
session_state=SessionState()
def callback(indata, frames, time, status):
    """Capture audio and send it to the server."""
    if status:
        print(f"Error: {status}")
    if not is_processing:
        audio_chunk = (indata * 32767).astype(np.int16)
        sio.emit("audio_chunk", audio_chunk.tobytes())

def stop_streaming():
    """Stop recording and streaming audio."""
    global stream
    try:
        if stream is not None:
            stream.stop()
            stream.close()
            stream = None
    except Exception as e:
        print(f"Error stopping stream: {e}")
    finally:
        stream = None

def start_streaming():
    """Start recording and streaming audio."""
    global stream
    try:
        if stream is None:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                callback=callback,
                blocksize=CHUNK_SIZE
            )
            stream.start()
            print("🎤 Recording... Press Ctrl+C to stop")
    except Exception as e:
        print(f"Error starting stream: {e}")
        stream = None
        stop_streaming()

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
    global transcription_text
    transcription_text = text
    #print(transcription_text)
    session_state.transcription=transcription_text

@sio.event
def answer_received(answer):
    global assistant_answer
    assistant_answer = answer
    #print(assistant_answer)
    session_state.answer=assistant_answer
    
@sio.event
def download_url_received(url):
    global download_url
    download_url = url
    session_state.download_url = download_url

def main():
    st.title("Real-Time Voice Assistant")
    
    with st.sidebar:
        st.header("Controls")
        uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    
        if uploaded_file is not None:
            #st.write("File uploaded successfully!")
            if st.button("Process Document"):
                API_URL = "http://127.0.0.1:8001/upload"
                files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                response = requests.post(API_URL, files=files)
                if response.status_code == 200:
                    st.success("Document processed successfully!")
                else:
                    st.error("Failed to process document!s")
                    #st.write("Error: ", response.text)
        
        if st.button("Start Voice Chat"):
            sio.connect("http://localhost:5000")
            st.success("You Can Now Start Chatting")
            session_state.connected=True
    if uploaded_file is not None:
        if session_state.connected:
            while True:
                if session_state.transcription:
                    st.write(f"👤 **You:** {session_state.transcription}")
                    session_state.transcription=None
                if session_state.answer:
                    st.write(f"🤖 **Assistant:** {session_state.answer}")
                    session_state.answer=None
                if session_state.download_url:
                    global temp
                    file_name = os.path.basename(temp)
                    audio_response = requests.get(download_url)
                    if audio_response.status_code == 200:
                        with open(file_name, "wb") as file:
                            file.write(audio_response.content)
                        #print("before playsound")
                        playsound(file_name)
                        #print("after playsound")
                        processing_complete()
                        #print("after processing complete")
                        session_state.download_url=None
            

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.write(f"Error: {e}")
