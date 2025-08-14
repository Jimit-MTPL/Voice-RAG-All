import streamlit as st
import socketio
import sounddevice as sd
import numpy as np
import requests
import os
from queue import Queue
import threading

# Create message queues for thread-safe communication
message_queue = Queue()
audio_queue = Queue()

# Create a Socket.IO client
sio = socketio.Client()

# Audio recording settings
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
CHANNELS = 1

# Global state management
class GlobalState:
    def __init__(self):
        self.is_recording = False
        self.is_processing = False
        self.stream = None
        self.pending_messages = Queue()

global_state = GlobalState()

# Initialize session state at startup
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'current_audio' not in st.session_state:
    st.session_state.current_audio = None
if 'needs_rerun' not in st.session_state:
    st.session_state.needs_rerun = False

def process_pending_messages():
    """Process any pending messages in the queue"""
    while not global_state.pending_messages.empty():
        msg = global_state.pending_messages.get_nowait()
        if msg and 'messages' in st.session_state:
            st.session_state.messages.append(msg)
            st.session_state.needs_rerun = True
def stop_streaming():
    try:
        if global_state.stream is not None:
            global_state.stream.stop()
            global_state.stream.close()
            global_state.stream = None
    except Exception as e:
        print(f"Error stopping stream: {e}")
    finally:
        global_state.stream = None
def callback(indata, frames, time, status):
    if status:
        print(f"Error: {status}")
    if not global_state.is_processing and global_state.is_recording:
        audio_chunk = (indata * 32767).astype(np.int16)
        sio.emit("audio_chunk", audio_chunk.tobytes())
def start_streaming():
    try:
        if global_state.stream is None:
            global_state.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                callback=callback,
                blocksize=CHUNK_SIZE
            )
            global_state.stream.start()
    except Exception as e:
        print(f"Error starting stream: {e}")
        global_state.stream = None
        stop_streaming()
        
@sio.event
def connect():
    print("✅ Connected to server")
    global_state.is_recording = True
    start_streaming()

@sio.event
def disconnect():
    print("❌ Disconnected from server")
    global_state.is_recording = False
    stop_streaming()
@sio.event
def transcription_received(text):
    """Handle transcription in a thread-safe way"""
    global_state.pending_messages.put({
        "role": "user",
        "content": text
    })

@sio.event
def answer_received(answer):
    """Handle assistant responses in a thread-safe way"""
    global_state.pending_messages.put({
        "role": "assistant",
        "content": answer
    })

@sio.event
def processing_started():
    global_state.is_processing = True
    stop_streaming()

def processing_complete():
    global_state.is_processing = False
    if global_state.is_recording:
        stop_streaming()
        start_streaming()

@sio.event
def processing_error():
    global_state.is_processing = False
    if global_state.is_recording:
        stop_streaming()
        start_streaming()
@sio.event
def download_url_received(url):
    st.session_state.current_audio = url
    st.rerun()
def main():
    st.title("Interactive Chat with Voice")
    
    # Process any pending messages at the start of each Streamlit run
    process_pending_messages()
    
    # Reset the rerun flag if it was set
    if st.session_state.needs_rerun:
        st.session_state.needs_rerun = False
        st.rerun()
    
    # Sidebar for file upload
    with st.sidebar:
        st.header("Upload Document")
        uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
        
        if uploaded_file is not None:
            if st.button("Process Document"):
                API_URL = "http://127.0.0.1:8001/upload"
                files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                response = requests.post(API_URL, files=files)
                
                if response.status_code == 200:
                    st.success("Document processed successfully!")
                else:
                    st.error("Failed to process document")

    # Recording control
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Recording" if not global_state.is_recording else "Stop Recording"):
            if not global_state.is_recording:
                if not sio.connected:
                    sio.connect("http://localhost:5000")
            else:
                global_state.is_recording = False
                stop_streaming()
                if sio.connected:
                    sio.disconnect()
    
    # Main chat container with scrolling
    chat_container = st.container()
    
    # Display chat messages with styling
    with chat_container:
        st.markdown("""
            <style>
                .chat-message { 
                    padding: 10px; 
                    margin: 5px 0; 
                    border-radius: 5px; 
                }
                .user-message { 
                    background-color: #e6f3ff; 
                }
                .assistant-message { 
                    background-color: #f0f0f0; 
                }
            </style>
        """, unsafe_allow_html=True)
        
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="chat-message user-message">👤 <b>You:</b> {msg["content"]}</div>', 
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="chat-message assistant-message">🤖 <b>Assistant:</b> {msg["content"]}</div>', 
                    unsafe_allow_html=True
                )

    # Handle audio playback
    if st.session_state.current_audio:
        file_name = os.path.basename(st.session_state.current_audio)
        audio_response = requests.get(st.session_state.current_audio)
        
        if audio_response.status_code == 200:
            with open(file_name, "wb") as file:
                file.write(audio_response.content)
            
            # Create and display audio player
            audio_player = create_audio_player(file_name)
            st.components.v1.html(audio_player, height=100)
            
            # Reset current audio and complete processing
            st.session_state.current_audio = None
            processing_complete()

def create_audio_player(audio_file):
    """Create a custom audio player with controls"""
    audio_html = f"""
        <div style="position: fixed; bottom: 0; left: 0; right: 0; background-color: white; padding: 10px; border-top: 1px solid #ccc;">
            <audio id="audio-player" controls autoplay style="width: 100%;">
                <source src="{audio_file}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
        </div>
        <div style="height: 100px;"></div>
    """
    return audio_html

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Error: {e}")
        if sio.connected:
            sio.disconnect()