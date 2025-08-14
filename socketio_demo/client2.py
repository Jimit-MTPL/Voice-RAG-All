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