# import socketio
# import time
# # Create a Socket.IO client
# sio = socketio.Client()

# # Handle connection
# @sio.event
# def connect():
#     print("Connected to server")
#     sio.send("Hello from Client")  # Send a message after connecting

# # Handle messages from the server
# @sio.on("message")
# def on_message(data):
#     print(f"Server says: {data}")

# # Handle disconnection
# @sio.event
# def disconnect():
#     print("Disconnected from server")

# # Connect to the server
# sio.connect("http://localhost:5000")
# time.sleep(5)
# sio.disconnect()
# #sio.wait()

# import socketio
# import sounddevice as sd
# import numpy as np

# # Create a Socket.IO client
# sio = socketio.Client()

# # Audio recording settings
# SAMPLE_RATE = 16000  # Hz
# CHUNK_SIZE = 1024  # Size of each audio chunk
# CHANNELS = 1  # Mono audio

# @sio.event
# def connect():
#     print("Connected to server")
#     start_streaming()

# @sio.event
# def disconnect():
#     print("Disconnected from server")

# def callback(indata, frames, time, status):
#     """Callback function to capture audio chunks and send them to the server."""
#     if status:
#         print(f"Error: {status}")
#     sio.emit("audio_chunk", indata.tobytes())  # Send audio chunk to server

# def start_streaming():
#     """Starts real-time audio recording and streaming."""
#     print("Recording and streaming audio...")
#     with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback, blocksize=CHUNK_SIZE):
#         input("Press ENTER to stop recording...\n")  # Keep recording until user stops
#         sio.emit("end_audio")  # Notify server that recording is done

# # Connect and start sending audio
# sio.connect("http://localhost:5000")
# sio.wait()

import socketio
import sounddevice as sd
import numpy as np

# Create a Socket.IO client
sio = socketio.Client()

# Audio recording settings
SAMPLE_RATE = 16000  # Hz
CHUNK_SIZE = 1024  # Number of samples per chunk
CHANNELS = 1  # Mono audio

@sio.event
def connect():
    print("✅ Connected to server")
    start_streaming()

@sio.event
def disconnect():
    print("❌ Disconnected from server")

def callback(indata, frames, time, status):
    """Capture audio and send it to the server."""
    if status:
        print(f"Error: {status}")
    # Convert float32 data to int16 before sending
    audio_chunk = (indata * 32767).astype(np.int16)
    sio.emit("audio_chunk", audio_chunk.tobytes())  # Send as bytes

def start_streaming():
    """Start recording and streaming audio."""
    print("🎤 Recording... Press ENTER to stop")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32",
                        callback=callback, blocksize=CHUNK_SIZE):
        input()  # Wait for user to press ENTER
        sio.emit("end_audio")  # Notify server to save the file

# Connect and start streaming
sio.connect("http://localhost:5000")
sio.wait()
