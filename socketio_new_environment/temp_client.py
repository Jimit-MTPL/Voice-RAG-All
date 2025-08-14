import socketio
#import pyaudio
import numpy as np
from pydub import AudioSegment
from pydub.playback import play
import sys
import os
#from pydub import AudioSegment
#from pydub.playback import play
import sounddevice as sd

# Initialize Socket.IO client
sio = socketio.Client()

# Audio recording settings
CHUNK = 1024
#FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
#recording = False

is_processing = False
stream = None
def print_status(message):
    """Print status messages with clear formatting"""
    print(f"\n>>> {message}")

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
            print("🎤 Recording stopped")
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
                samplerate=RATE,
                channels=CHANNELS,
                dtype="float32",
                callback=callback,
                blocksize=CHUNK
            )
            stream.start()
            print("🎤 Recording... Press Ctrl+C to stop")
    except Exception as e:
        print(f"Error starting stream: {e}")
        stream = None
        # Try to clean up if there was an error
        stop_streaming()

def processing_complete():
    """Server has finished processing the audio"""
    global is_processing
    is_processing = False
    #print("✅ Processing complete. You can speak now.")
    stop_streaming()
    start_streaming()

@sio.event
def connect():
    print_status("Connected to translation server")
    print_status("Waiting for available languages...")


@sio.event
def available_languages(data):
    print_status("Available Languages:")
    languages = data['languages']
    
    for i, lang in enumerate(languages, 1):
        print(f"  {i}. {lang}")

    try:
        src_idx = int(input("\nEnter number for source language: ")) - 1
        tgt_idx = int(input("Enter number for target language: ")) - 1

        if 0 <= src_idx < len(languages) and 0 <= tgt_idx < len(languages):
            src_lang = languages[src_idx]
            tgt_lang = languages[tgt_idx]
            print_status(f"Selected: {src_lang} → {tgt_lang}")
            sio.emit('start_translation', {'src_lang': src_lang, 'tgt_lang': tgt_lang})
        else:
            print_status("Invalid selection. Please restart the client.")
            sys.exit(1)
    except ValueError:
        print_status("Invalid input. Please restart the client.")
        sys.exit(1)


@sio.event
def config_received(data):
    #global stream
    if data.get('status') == 'ok':
        print_status("Ready to record!")
        print_status("Speak into your microphone")
        print_status("Press Ctrl+C to stop recording")
        #stream = True
        start_streaming()
    else:
        print_status(f"Error: {data.get('message', 'Configuration failed')}")
        sys.exit(1)

@sio.event
def transcription_received(data):
    print_status(f"Original: {data['text']}")


@sio.event
def translation_received(data):
    print_status(f"Translated: {data['text']}")

@sio.event
def processing_started():
    print_status("Processing your speech...")
    global is_processing
    is_processing = True
    stop_streaming()

@sio.event
def processing_error(data):
    print_status(f"Error: {data.get('error', 'Unknown error')}")
    global is_processing
    is_processing = False
    stop_streaming()
    start_streaming()

@sio.event
def audio_ready(data):
    print("Playing translated audio...")
    try:
        file_path = data['file']  # Ensure this is the correct path to the WAV file
        filename = os.path.basename(file_path)  # Extract only the filename

        print(f"Received file path: {file_path}")
        print(f"Extracted filename: {filename}")

        # Play the audio
        audio = AudioSegment.from_wav(file_path)
        play(audio)

        # Construct the correct download link
        download_link = f"http://127.0.0.1:5001/download/{filename}"
        print(f"Audio Download link: {download_link}")
        processing_complete()
    except Exception as e:
        print(f"Error playing audio: {str(e)}")

# def start_recording():
#     """Start recording audio from microphone"""
#     global recording

#     p = pyaudio.PyAudio()
#     stream = p.open(
#         format=FORMAT,
#         channels=CHANNELS,
#         rate=RATE,
#         input=True,
#         frames_per_buffer=CHUNK
#     )

#     try:
#         while recording:
#             data = stream.read(CHUNK)
#             sio.emit('audio_chunk', data)
#     except KeyboardInterrupt:
#         print_status("Stopping recording...")
#     finally:
#         recording = False
#         stream.stop_stream()
#         stream.close()
#         p.terminate()
#         sio.disconnect()
#         print_status("Disconnected from server")

def main():
    """Main function to run the client"""
    print_status("Voice Translation Console Client")
    print_status("Connecting to server...")

    try:
        sio.connect('http://localhost:5000')
        sio.wait()
    except Exception as e:
        print_status(f"Connection error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_status("\nExiting...")
        sys.exit(0)


import socketio
import pyaudio
import numpy as np
from pydub import AudioSegment
from pydub.playback import play
import sys
import os
from pydub import AudioSegment
from pydub.playback import play


# Initialize Socket.IO client
sio = socketio.Client()

# Audio recording settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
recording = False


def print_status(message):
    """Print status messages with clear formatting"""
    print(f"\n>>> {message}")


@sio.event
def connect():
    print_status("Connected to translation server")
    print_status("Waiting for available languages...")


@sio.event
def available_languages(data):
    print_status("Available Languages:")
    languages = data['languages']
    
    for i, lang in enumerate(languages, 1):
        print(f"  {i}. {lang}")

    try:
        src_idx = int(input("\nEnter number for source language: ")) - 1
        tgt_idx = int(input("Enter number for target language: ")) - 1

        if 0 <= src_idx < len(languages) and 0 <= tgt_idx < len(languages):
            src_lang = languages[src_idx]
            tgt_lang = languages[tgt_idx]
            print_status(f"Selected: {src_lang} → {tgt_lang}")
            sio.emit('start_translation', {'src_lang': src_lang, 'tgt_lang': tgt_lang})
        else:
            print_status("Invalid selection. Please restart the client.")
            sys.exit(1)
    except ValueError:
        print_status("Invalid input. Please restart the client.")
        sys.exit(1)


@sio.event
def config_received(data):
    global recording
    if data.get('status') == 'ok':
        print_status("Ready to record!")
        print_status("Speak into your microphone")
        print_status("Press Ctrl+C to stop recording")
        recording = True
        start_recording()
    else:
        print_status(f"Error: {data.get('message', 'Configuration failed')}")
        sys.exit(1)


@sio.event
def processing_started():
    print_status("Processing your speech...")


@sio.event
def transcription_received(data):
    print_status(f"Original: {data['text']}")


@sio.event
def translation_received(data):
    print_status(f"Translated: {data['text']}")

@sio.event
def audio_ready(data):
    print("Playing translated audio...")
    try:
        file_path = data['file']  # Ensure this is the correct path to the WAV file
        filename = os.path.basename(file_path)  # Extract only the filename

        print(f"Received file path: {file_path}")
        print(f"Extracted filename: {filename}")

        # Play the audio
        audio = AudioSegment.from_wav(file_path)
        play(audio)

        # Construct the correct download link
        download_link = f"http://127.0.0.1:5001/download/{filename}"
        print(f"Audio Download link: {download_link}")

    except Exception as e:
        print(f"Error playing audio: {str(e)}")



@sio.event
def processing_error(data):
    print_status(f"Error: {data.get('error', 'Unknown error')}")


def start_recording():
    """Start recording audio from microphone"""
    global recording

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    try:
        while recording:
            data = stream.read(CHUNK)
            sio.emit('audio_chunk', data)
    except KeyboardInterrupt:
        print_status("Stopping recording...")
    finally:
        recording = False
        stream.stop_stream()
        stream.close()
        p.terminate()
        sio.disconnect()
        print_status("Disconnected from server")


def main():
    """Main function to run the client"""
    print_status("Voice Translation Console Client")
    print_status("Connecting to server...")

    try:
        sio.connect('http://localhost:5000')
        sio.wait()
    except Exception as e:
        print_status(f"Connection error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_status("\nExiting...")
        sys.exit(0)


import socketio
import pyaudio
import numpy as np
from pydub import AudioSegment
from pydub.playback import play
import sys
import os

# Initialize Socket.IO client
sio = socketio.Client()

# Audio recording settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
recording = False


def print_status(message):
    """Print status messages with clear formatting"""
    print(f"\n>>> {message}")


@sio.event
def connect():
    print_status("Connected to translation server")
    print_status("Waiting for available languages...")


@sio.event
def available_languages(data):
    print_status("Available Languages:")
    languages = data['languages']
    
    for i, lang in enumerate(languages, 1):
        print(f"  {i}. {lang}")

    try:
        src_idx = int(input("\nEnter number for source language: ")) - 1
        tgt_idx = int(input("Enter number for target language: ")) - 1

        if 0 <= src_idx < len(languages) and 0 <= tgt_idx < len(languages):
            src_lang = languages[src_idx]
            tgt_lang = languages[tgt_idx]
            print_status(f"Selected: {src_lang} → {tgt_lang}")
            sio.emit('start_translation', {'src_lang': src_lang, 'tgt_lang': tgt_lang})
        else:
            print_status("Invalid selection. Please restart the client.")
            sys.exit(1)
    except ValueError:
        print_status("Invalid input. Please restart the client.")
        sys.exit(1)


@sio.event
def config_received(data):
    """Start recording when configuration is received"""
    global recording
    if data.get('status') == 'ok':
        print_status("Ready to record!")
        print_status("Speak into your microphone")
        print_status("Press Ctrl+C to stop recording")
        recording = True
        start_recording()
    else:
        print_status(f"Error: {data.get('message', 'Configuration failed')}")
        sys.exit(1)


@sio.event
def processing_started():
    """Stop recording when processing starts"""
    global recording
    print_status("Processing your speech...")
    recording = False  # Stop recording


@sio.event
def transcription_received(data):
    print_status(f"Original: {data['text']}")


@sio.event
def translation_received(data):
    print_status(f"Translated: {data['text']}")


@sio.event
def audio_ready(data):
    """Play the translated audio and restart recording after playback"""
    print_status("Playing translated audio...")
    try:
        file_path = data['file']
        filename = os.path.basename(file_path)

        print(f"Received file path: {file_path}")
        print(f"Extracted filename: {filename}")

        audio = AudioSegment.from_wav(file_path)
        play(audio)

        download_link = f"http://127.0.0.1:5001/download/{filename}"
        print_status(f"Audio Download link: {download_link}")

        # Restart recording after playback is complete
        processing_complete()

    except Exception as e:
        print(f"Error playing audio: {str(e)}")
        print_status("Restarting recording due to playback error...")
        start_recording()  # Restart recording if error occurs


@sio.event
def processing_error(data):
    """Restart recording if an error occurs"""
    print_status(f"Error: {data.get('error', 'Unknown error')}")
    print_status("Restarting recording...")
    start_recording()


def start_recording():
    """Start recording audio from microphone"""
    global recording
    recording = True

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    try:
        while recording:
            data = stream.read(CHUNK)
            sio.emit('audio_chunk', data)
    except KeyboardInterrupt:
        print_status("Stopping recording...")
    finally:
        recording = False
        stream.stop_stream()
        stream.close()
        p.terminate()


def processing_complete():
    """Restart recording after playback is complete"""
    print_status("Restarting recording after playback...")
    start_recording()


@sio.event
def disconnect():
    """Handle disconnection and attempt to reconnect"""
    print_status("Disconnected from server! Reconnecting...")
    try:
        sio.connect('http://localhost:5000')
    except Exception as e:
        print_status(f"Reconnection failed: {str(e)}")


def main():
    """Main function to run the client"""
    print_status("Voice Translation Console Client")
    print_status("Connecting to server...")

    try:
        sio.connect('http://localhost:5000')
        sio.wait()
    except Exception as e:
        print_status(f"Connection error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_status("\nExiting...")
        sys.exit(0)