import socketio
import sounddevice as sd
import numpy as np

# Create a Socket.IO client
sio = socketio.Client()

# Audio recording settings
SAMPLE_RATE = 16000  # Hz
CHUNK_SIZE = 1024  # Number of samples per chunk
CHANNELS = 1  # Mono audio

# Add state tracking
is_processing = False
stream = None

def callback(indata, frames, time, status):
    """Capture audio and send it to the server."""
    if status:
        print(f"Error: {status}")
    if not is_processing:
        # Convert float32 data to int16 before sending
        audio_chunk = (indata * 32767).astype(np.int16)
        sio.emit("audio_chunk", audio_chunk.tobytes())
def stop_streaming():
    """Stop recording and streaming audio."""
    global stream
    #print("stream at start of stop streaming!!!!!!(should not be none)", stream)
    try:
        if stream is not None:
            stream.stop()
            stream.close()
            stream = None
    except Exception as e:
        print(f"Error stopping stream: {e}")
    finally:
        stream = None
        #print("stream at end of stop streaming!!!!!!", stream)

def start_streaming():
    """Start recording and streaming audio."""
    global stream
    #print("stream at start of start streaming!!!!!!(should be none)", stream)
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
        # Try to clean up if there was an error
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
    #print("⏳ Processing audio... Please wait...")
    stop_streaming()

@sio.event
def processing_complete():
    """Server has finished processing the audio"""
    global is_processing
    is_processing = False
    #print("✅ Processing complete. You can speak now.")
    stop_streaming()
    start_streaming()

@sio.event
def processing_error():
    """Server encountered an error during processing"""
    global is_processing
    is_processing = False
    #print("❌ Error during processing. You can speak now.")
    stop_streaming()
    start_streaming()


try:
    # Connect and start streaming
    sio.connect("http://localhost:5000")
    while True:
        try:
            sio.sleep(1)
        except KeyboardInterrupt:
            break
finally:
    stop_streaming()
    sio.disconnect()