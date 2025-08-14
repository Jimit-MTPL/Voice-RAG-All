# import socketio
# import eventlet

# # Create a Socket.IO server
# sio = socketio.Server(cors_allowed_origins="*")
# app = socketio.WSGIApp(sio)

# # Handle a new client connection
# @sio.event
# def connect(sid, environ):
#     print(f"Client {sid} connected")

# # Handle incoming messages
# @sio.event
# def message(sid, data):
#     print(f"Received message from {sid}: {data}")
#     sio.send(f"Server received: {data}")  # Send response back to client

# # Handle client disconnection
# @sio.event
# def disconnect(sid):
#     print(f"Client {sid} disconnected")

# # Run the server
# if __name__ == "__main__":
#     eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)

# import socketio
# import eventlet
# import numpy as np
# import wave

# # Initialize Socket.IO server
# sio = socketio.Server(cors_allowed_origins="*")
# app = socketio.WSGIApp(sio)

# # Sample rate and audio file settings
# SAMPLE_RATE = 16000  # Hz
# CHANNELS = 1
# OUTPUT_FILE = "received_audio.wav"

# audio_data = []  # Store received audio chunks

# @sio.event
# def connect(sid, environ):
#     print(f"Client {sid} connected")

# @sio.event
# def audio_chunk(sid, data):
#     """Handles incoming audio chunks from the client."""
#     global audio_data
#     audio_array = np.frombuffer(data, dtype=np.int16)
#     audio_data.append(audio_array)
#     print(f"Received audio chunk from {sid}")

# @sio.event
# def end_audio(sid):
#     """Handles the end of the audio stream and saves the file."""
#     global audio_data
#     if not audio_data:
#         print("No audio data received.")
#         return

#     # Convert list of NumPy arrays to a single array
#     final_audio = np.concatenate(audio_data, axis=0)

#     # Save the audio as a WAV file
#     with wave.open(OUTPUT_FILE, "wb") as wf:
#         wf.setnchannels(CHANNELS)
#         wf.setsampwidth(2)  # 16-bit audio
#         wf.setframerate(SAMPLE_RATE)
#         wf.writeframes(final_audio.tobytes())

#     print(f"Audio saved to {OUTPUT_FILE}")
#     audio_data = []  # Reset buffer

# @sio.event
# def disconnect(sid):
#     print(f"Client {sid} disconnected")

# # Start the server
# if __name__ == "__main__":
#     print("Starting server on port 5000...")
#     eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# import socketio
# import eventlet
# import numpy as np
# import wave

# # Initialize Socket.IO server
# sio = socketio.Server(cors_allowed_origins="*")
# app = socketio.WSGIApp(sio)

# # Audio settings
# SAMPLE_RATE = 16000  # Hz
# CHANNELS = 1
# SAMPLE_WIDTH = 2  # 16-bit audio
# OUTPUT_FILE = "received_audio.wav"

# audio_data = []  # Buffer for audio chunks

# @sio.event
# def connect(sid, environ):
#     print(f"Client {sid} connected")

# @sio.event
# def audio_chunk(sid, data):
#     """Handles incoming audio chunks from the client."""
#     global audio_data
#     audio_array = np.frombuffer(data, dtype=np.int16)  # Convert bytes to NumPy array
#     audio_data.append(audio_array)
#     print(f"Received audio chunk from {sid}, Samples: {len(audio_array)}")

# @sio.event
# def end_audio(sid):
#     """Handles the end of the audio stream and saves the file."""
#     global audio_data
#     if not audio_data:
#         print("No audio data received.")
#         return

#     # Concatenate all received chunks
#     final_audio = np.concatenate(audio_data, axis=0)

#     # Save to a WAV file
#     with wave.open(OUTPUT_FILE, "wb") as wf:
#         wf.setnchannels(CHANNELS)
#         wf.setsampwidth(SAMPLE_WIDTH)  # 16-bit audio = 2 bytes per sample
#         wf.setframerate(SAMPLE_RATE)
#         wf.writeframes(final_audio.tobytes())

#     print(f"✅ Audio saved successfully as {OUTPUT_FILE}")
#     audio_data = []  # Reset buffer

# @sio.event
# def disconnect(sid):
#     print(f"Client {sid} disconnected")

# # Start the server
# if __name__ == "__main__":
#     print("🎤 Starting server on port 5000...")
#     eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------
import socketio
import eventlet
import numpy as np
import wave
import time
from datetime import datetime
# Initialize Socket.IO server
sio = socketio.Server(cors_allowed_origins="*")
app = socketio.WSGIApp(sio)

# Audio settings
SAMPLE_RATE = 16000  # Hz
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit audio
OUTPUT_FILE = "received_audio.wav"
SAVE_DIR = "audio_files" 
# Silence detection settings
SILENCE_THRESHOLD = 500  # Adjust based on microphone sensitivity
SILENCE_DURATION = 5.0  # Seconds of silence before saving

audio_data = []  # Buffer for audio chunks
last_audio_time = time.time()  # Track last non-silent audio time

@sio.event
def connect(sid, environ):
    print(f"✅ Client {sid} connected")

@sio.event
def audio_chunk(sid, data):
    """Handles incoming audio chunks and detects silence."""
    global audio_data, last_audio_time

    # Convert bytes to NumPy int16 array
    audio_array = np.frombuffer(data, dtype=np.int16)

    # Calculate volume (mean absolute amplitude)
    volume = np.mean(np.abs(audio_array))

    # Check if the audio is silent
    if volume > SILENCE_THRESHOLD:
        last_audio_time = time.time()  # Reset silence timer
        audio_data.append(audio_array)
        print(f"🎤 Received audio chunk from {sid}, Volume: {volume:.2f}")
    else:
        print(f"🔇 Silence detected (Volume: {volume:.2f})")

    # Check if silence has lasted for the required duration
    if time.time() - last_audio_time >= SILENCE_DURATION and audio_data:
        save_audio()
        audio_data.clear()  # Reset buffer

def save_audio():
    """Saves the received audio chunks into a WAV file."""
    if not audio_data:
        print("⚠ No audio data to save.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    file_name = f"{SAVE_DIR}/audio_{timestamp}.wav"

    final_audio = np.concatenate(audio_data, axis=0)

    with wave.open(file_name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(final_audio.tobytes())
    # with wave.open(OUTPUT_FILE, "wb") as wf:
    #     wf.setnchannels(CHANNELS)
    #     wf.setsampwidth(SAMPLE_WIDTH)
    #     wf.setframerate(SAMPLE_RATE)
    #     wf.writeframes(final_audio.tobytes())

    print(f"✅ Audio saved as {OUTPUT_FILE}")

@sio.event
def disconnect(sid):
    print(f"❌ Client {sid} disconnected")

# Start the server
if __name__ == "__main__":
    print("🎤 Starting server on port 5000...")
    eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)
# #-------------------------------------------------------------------------------------------------------------------------------------------------------------------------



