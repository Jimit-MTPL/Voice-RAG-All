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
class SessionState:
    def __init__(self):
        self.transcription = None
        self.answer = None
        self.download_url = None
        self.connected = False
        self.file_name= None
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
    session_state.transcription=transcription_text

@sio.event
def answer_received(answer):
    global assistant_answer
    assistant_answer = answer
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
        uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf","txt","csv"])
    
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
        
            if st.button("Start Voice Chat"):
                sio.connect("http://localhost:5000")
                st.success("You Can Now Start Chatting")
                session_state.connected=True
            if st.button("Stop Voice Chat"):
                sio.disconnect()
                st.success("Chat is Ended")
    if uploaded_file is not None:
        if session_state.connected:
            while True:
                if session_state.transcription:
                    st.markdown(
                    f"""
                    <div style="padding: 10px; background-color: #f0f2f6; border-radius: 10px; margin-bottom: 10px; color: #333;">
                        <b>👤 You:</b> {session_state.transcription}
                    </div>
                    """,
                    unsafe_allow_html=True
                    )

                    session_state.transcription=None
                if session_state.answer:
                    st.markdown(
                    f"""
                    <div style="padding: 10px; background-color: #e8f5e9; border-radius: 10px; margin-bottom: 10px; color: #333;">
                        <b>🤖 Assistant:</b> {session_state.answer}
                    </div>
                    """,
                    unsafe_allow_html=True
                    )

                    session_state.answer=None
                if session_state.download_url:
                    session_state.file_name = os.path.basename(session_state.download_url)
                    audio_response = requests.get(session_state.download_url)
                    if audio_response.status_code == 200:
                        with open(session_state.file_name, "wb") as file:
                            file.write(audio_response.content)
                        # st.audio(session_state.file_name)
                        playsound(session_state.file_name)
                        processing_complete()
                        #os.remove(file_name)
                        session_state.download_url=None
                if session_state.file_name:
                    os.remove(session_state.file_name)
                    session_state.file_name=None                    

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.write(f"Error: {e}")
