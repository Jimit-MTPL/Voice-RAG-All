# import socketio
# import eventlet
# import numpy as np
# import wave
# import time
# from datetime import datetime
# import os
# from collections import deque

# # Initialize Socket.IO server
# sio = socketio.Server(cors_allowed_origins="*")
# app = socketio.WSGIApp(sio)

# # Audio settings
# SAMPLE_RATE = 16000  # Hz
# CHANNELS = 1
# SAMPLE_WIDTH = 2  # 16-bit audio
# SAVE_DIR = "audio_files"

# # Ensure save directory exists
# os.makedirs(SAVE_DIR, exist_ok=True)

# # Improved silence detection settings
# SILENCE_THRESHOLD = 500  # Adjust based on microphone sensitivity
# SILENCE_DURATION = 2.0  # Seconds of silence before saving
# MIN_AUDIO_DURATION = 0.5  # Minimum duration (in seconds) for saved audio
# CHUNK_DURATION = 0.064  # Duration of each chunk (1024 samples at 16kHz)

# class AudioBuffer:
#     def __init__(self):
#         self.buffer = []  # Main buffer for audio data
#         self.is_recording = False
#         self.silence_start = None
#         self.last_active_time = None
#         # Buffer for analyzing recent volume levels
#         self.volume_window = deque(maxlen=int(0.5 / CHUNK_DURATION))  # 0.5 second window
        
#     def add_chunk(self, audio_array):
#         volume = np.mean(np.abs(audio_array))
#         self.volume_window.append(volume)
#         current_time = time.time()
        
#         # Determine if current chunk is silent using a rolling average
#         is_silent = np.mean(self.volume_window) < SILENCE_THRESHOLD
        
#         if not is_silent:
#             if not self.is_recording:
#                 self.is_recording = True
#                 self.silence_start = None
#             self.last_active_time = current_time
#             self.buffer.append(audio_array)
#         else:
#             if self.is_recording:
#                 if self.silence_start is None:
#                     self.silence_start = current_time
#                 self.buffer.append(audio_array)  # Keep adding silent chunks for natural fade-out
                
#                 # Check if silence duration exceeds threshold
#                 if (current_time - self.silence_start) >= SILENCE_DURATION:
#                     return self.save_buffer()
        
#         return False
    
#     def save_buffer(self):
#         if not self.buffer:
#             return False
            
#         # Calculate audio duration
#         total_samples = sum(len(chunk) for chunk in self.buffer)
#         duration = total_samples / SAMPLE_RATE
        
#         # Only save if audio duration meets minimum requirement
#         if duration >= MIN_AUDIO_DURATION:
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
#             file_name = f"{SAVE_DIR}/audio_{timestamp}.wav"
            
#             # Trim excess silence from the end
#             if self.silence_start and self.last_active_time:
#                 silence_samples = int(SILENCE_DURATION * SAMPLE_RATE)
#                 total_samples = sum(len(chunk) for chunk in self.buffer)
#                 if total_samples > silence_samples:
#                     keep_samples = total_samples - silence_samples
#                     accumulated = 0
#                     trimmed_buffer = []
#                     for chunk in self.buffer:
#                         if accumulated + len(chunk) <= keep_samples:
#                             trimmed_buffer.append(chunk)
#                             accumulated += len(chunk)
#                         else:
#                             remaining = keep_samples - accumulated
#                             if remaining > 0:
#                                 trimmed_buffer.append(chunk[:remaining])
#                             break
#                     self.buffer = trimmed_buffer

#             # Save the audio file
#             final_audio = np.concatenate(self.buffer, axis=0)
#             with wave.open(file_name, "wb") as wf:
#                 wf.setnchannels(CHANNELS)
#                 wf.setsampwidth(SAMPLE_WIDTH)
#                 wf.setframerate(SAMPLE_RATE)
#                 wf.writeframes(final_audio.tobytes())
            
#             print(f"✅ Audio saved as {file_name} (Duration: {duration:.2f}s)")
#             self.reset()
#             return True
            
#         self.reset()
#         return False
    
#     def reset(self):
#         self.buffer = []
#         self.is_recording = False
#         self.silence_start = None
#         self.last_active_time = None
#         self.volume_window.clear()

# # Create audio buffer instance
# audio_buffer = AudioBuffer()

# @sio.event
# def connect(sid, environ):
#     print(f"✅ Client {sid} connected")

# @sio.event
# def audio_chunk(sid, data):
#     """Handles incoming audio chunks and detects silence."""
#     audio_array = np.frombuffer(data, dtype=np.int16)
#     if audio_buffer.add_chunk(audio_array):
#         print(f"🎤 Finished recording from {sid}")

# @sio.event
# def disconnect(sid):
#     print(f"❌ Client {sid} disconnected")
#     # Save any remaining audio
#     if audio_buffer.buffer:
#         audio_buffer.save_buffer()

# # Start the server
# if __name__ == "__main__":
#     print("🎤 Starting server on port 5000...")
#     eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)

# import socketio
# import eventlet
# import numpy as np
# import wave
# import time
# from datetime import datetime
# import os
# from collections import deque

# # Initialize Socket.IO server
# sio = socketio.Server(cors_allowed_origins="*")
# app = socketio.WSGIApp(sio)

# # Audio settings
# SAMPLE_RATE = 16000  # Hz
# CHANNELS = 1
# SAMPLE_WIDTH = 2  # 16-bit audio
# SAVE_DIR = "audio_files"

# # Ensure save directory exists
# os.makedirs(SAVE_DIR, exist_ok=True)

# # Stricter audio detection settings
# SILENCE_THRESHOLD = 1000  # Increased threshold for better noise filtering
# SILENCE_DURATION = 2.0  # Seconds of silence before saving
# MIN_AUDIO_DURATION = 2.0  # Minimum duration (in seconds) for saved audio
# MAX_AUDIO_DURATION = 30.0  # Maximum duration (in seconds) for saved audio
# CHUNK_DURATION = 0.064  # Duration of each chunk (1024 samples at 16kHz)
# MIN_VALID_CHUNKS = 3  # Minimum number of valid (non-silent) chunks required

# class AudioBuffer:
#     def __init__(self):
#         self.buffer = []
#         self.is_recording = False
#         self.silence_start = None
#         self.last_active_time = None
#         self.volume_window = deque(maxlen=int(1.0 / CHUNK_DURATION))  # 1 second window
#         self.valid_chunk_count = 0
#         self.recording_start_time = None
        
#     def add_chunk(self, audio_array):
#         current_time = time.time()
        
#         # Calculate volume using RMS (Root Mean Square) for better noise detection
#         volume_rms = np.sqrt(np.mean(np.square(audio_array)))
#         self.volume_window.append(volume_rms)
        
#         # Use moving average for more stable volume detection
#         avg_volume = np.mean(self.volume_window)
#         is_silent = avg_volume < SILENCE_THRESHOLD
        
#         # Start recording only if we detect significant sound
#         if not is_silent:
#             if not self.is_recording:
#                 self.is_recording = True
#                 self.recording_start_time = current_time
#                 self.valid_chunk_count = 0
            
#             self.last_active_time = current_time
#             self.buffer.append(audio_array)
#             self.valid_chunk_count += 1
#             self.silence_start = None
#         else:
#             if self.is_recording:
#                 if self.silence_start is None:
#                     self.silence_start = current_time
#                 self.buffer.append(audio_array)
                
#                 # Check conditions for saving
#                 silence_duration = current_time - self.silence_start
#                 total_duration = current_time - self.recording_start_time
                
#                 if silence_duration >= SILENCE_DURATION:
#                     return self.save_buffer()
#                 elif total_duration >= MAX_AUDIO_DURATION:
#                     return self.save_buffer()
        
#         return False
    
#     def save_buffer(self):
#         if not self.buffer or self.valid_chunk_count < MIN_VALID_CHUNKS:
#             self.reset()
#             return False
            
#         # Calculate audio duration
#         total_samples = sum(len(chunk) for chunk in self.buffer)
#         duration = total_samples / SAMPLE_RATE
        
#         # Only save if duration meets requirements
#         if MIN_AUDIO_DURATION <= duration <= MAX_AUDIO_DURATION:
#             # Trim excess silence from the end
#             if self.silence_start and self.last_active_time:
#                 keep_duration = (self.last_active_time - self.recording_start_time) + 0.5  # Keep 0.5s of trailing silence
#                 keep_samples = int(keep_duration * SAMPLE_RATE)
                
#                 trimmed_buffer = []
#                 accumulated_samples = 0
                
#                 for chunk in self.buffer:
#                     if accumulated_samples + len(chunk) <= keep_samples:
#                         trimmed_buffer.append(chunk)
#                         accumulated_samples += len(chunk)
#                     else:
#                         remaining = keep_samples - accumulated_samples
#                         if remaining > 0:
#                             trimmed_buffer.append(chunk[:remaining])
#                         break
                
#                 final_audio = np.concatenate(trimmed_buffer, axis=0)
#             else:
#                 final_audio = np.concatenate(self.buffer, axis=0)
            
#             # Additional noise check on final audio
#             final_rms = np.sqrt(np.mean(np.square(final_audio)))
#             if final_rms < SILENCE_THRESHOLD:
#                 self.reset()
#                 return False
            
#             # Save the file
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
#             file_name = f"{SAVE_DIR}/audio_{timestamp}.wav"
            
#             with wave.open(file_name, "wb") as wf:
#                 wf.setnchannels(CHANNELS)
#                 wf.setsampwidth(SAMPLE_WIDTH)
#                 wf.setframerate(SAMPLE_RATE)
#                 wf.writeframes(final_audio.tobytes())
            
#             print(f"✅ Audio saved as {file_name} (Duration: {duration:.2f}s, RMS: {final_rms:.2f})")
#             self.reset()
#             return True
            
#         self.reset()
#         return False
    
#     def reset(self):
#         self.buffer = []
#         self.is_recording = False
#         self.silence_start = None
#         self.last_active_time = None
#         self.volume_window.clear()
#         self.valid_chunk_count = 0
#         self.recording_start_time = None

# # Create audio buffer instance
# audio_buffer = AudioBuffer()

# @sio.event
# def connect(sid, environ):
#     print(f"✅ Client {sid} connected")

# @sio.event
# def audio_chunk(sid, data):
#     """Handles incoming audio chunks and detects silence."""
#     audio_array = np.frombuffer(data, dtype=np.int16)
#     if audio_buffer.add_chunk(audio_array):
#         print(f"🎤 Finished recording from {sid}")

# @sio.event
# def disconnect(sid):
#     print(f"❌ Client {sid} disconnected")
#     if audio_buffer.buffer:
#         audio_buffer.save_buffer()

# if __name__ == "__main__":
#     print("🎤 Starting server on port 5000...")
#     eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)




#-----------------------------------------BEST------------------------------------------------
# import socketio
# import eventlet
# import numpy as np
# import wave
# import time
# from datetime import datetime
# import os
# from collections import deque

# # Initialize Socket.IO server
# sio = socketio.Server(cors_allowed_origins="*")
# app = socketio.WSGIApp(sio)

# # Audio settings
# SAMPLE_RATE = 16000  # Hz
# CHANNELS = 1
# SAMPLE_WIDTH = 2  # 16-bit audio
# SAVE_DIR = "audio_files"

# # Ensure save directory exists
# os.makedirs(SAVE_DIR, exist_ok=True)

# # Stricter audio detection settings
# SILENCE_THRESHOLD = 1000  # Increased threshold for better noise filtering
# SILENCE_DURATION = 2.0  # Seconds of silence before saving
# MIN_AUDIO_DURATION = 2.0  # Minimum duration (in seconds) for saved audio
# MAX_AUDIO_DURATION = 30.0  # Maximum duration (in seconds) for saved audio
# CHUNK_DURATION = 0.064  # Duration of each chunk (1024 samples at 16kHz)
# MIN_VALID_CHUNKS = 3  # Minimum number of valid (non-silent) chunks required

# class AudioBuffer:
#     def __init__(self):
#         self.buffer = []
#         self.is_recording = False
#         self.silence_start = None
#         self.last_active_time = None
#         self.volume_window = deque(maxlen=int(1.0 / CHUNK_DURATION))  # 1 second window
#         self.valid_chunk_count = 0
#         self.recording_start_time = None
        
#     def calculate_rms(self, audio_array):
#         """Safely calculate RMS value with handling for empty or invalid arrays."""
#         if len(audio_array) == 0:
#             return 0.0
#         # Convert to float64 to prevent overflow
#         audio_float = audio_array.astype(np.float64)
#         squared = np.square(audio_float)
#         mean_squared = np.mean(squared)
#         # Handle negative values that might occur due to floating point errors
#         if mean_squared < 0:
#             return 0.0
#         return np.sqrt(mean_squared)
        
#     def add_chunk(self, audio_array):
#         current_time = time.time()
        
#         # Calculate volume using safe RMS calculation
#         volume_rms = self.calculate_rms(audio_array)
#         self.volume_window.append(volume_rms)
        
#         # Use moving average for more stable volume detection
#         avg_volume = np.mean(list(self.volume_window)) if self.volume_window else 0
#         is_silent = avg_volume < SILENCE_THRESHOLD
        
#         # Start recording only if we detect significant sound
#         if not is_silent:
#             if not self.is_recording:
#                 self.is_recording = True
#                 self.recording_start_time = current_time
#                 self.valid_chunk_count = 0
            
#             self.last_active_time = current_time
#             self.buffer.append(audio_array)
#             self.valid_chunk_count += 1
#             self.silence_start = None
#         else:
#             if self.is_recording:
#                 if self.silence_start is None:
#                     self.silence_start = current_time
#                 self.buffer.append(audio_array)
                
#                 # Check conditions for saving
#                 silence_duration = current_time - self.silence_start
#                 total_duration = current_time - self.recording_start_time
                
#                 if silence_duration >= SILENCE_DURATION:
#                     return self.save_buffer()
#                 elif total_duration >= MAX_AUDIO_DURATION:
#                     return self.save_buffer()
        
#         return False
    
#     def save_buffer(self):
#         if not self.buffer or self.valid_chunk_count < MIN_VALID_CHUNKS:
#             self.reset()
#             return False
            
#         # Calculate audio duration
#         total_samples = sum(len(chunk) for chunk in self.buffer)
#         duration = total_samples / SAMPLE_RATE
        
#         # Only save if duration meets requirements
#         if MIN_AUDIO_DURATION <= duration <= MAX_AUDIO_DURATION:
#             # Trim excess silence from the end
#             if self.silence_start and self.last_active_time:
#                 keep_duration = (self.last_active_time - self.recording_start_time) + 0.5  # Keep 0.5s of trailing silence
#                 keep_samples = int(keep_duration * SAMPLE_RATE)
                
#                 trimmed_buffer = []
#                 accumulated_samples = 0
                
#                 for chunk in self.buffer:
#                     if accumulated_samples + len(chunk) <= keep_samples:
#                         trimmed_buffer.append(chunk)
#                         accumulated_samples += len(chunk)
#                     else:
#                         remaining = keep_samples - accumulated_samples
#                         if remaining > 0:
#                             trimmed_buffer.append(chunk[:remaining])
#                         break
                
#                 final_audio = np.concatenate(trimmed_buffer, axis=0)
#             else:
#                 final_audio = np.concatenate(self.buffer, axis=0)
            
#             # Additional noise check on final audio using safe RMS calculation
#             final_rms = self.calculate_rms(final_audio)
#             if final_rms < SILENCE_THRESHOLD:
#                 self.reset()
#                 return False
            
#             # Save the file
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
#             file_name = f"{SAVE_DIR}/audio_{timestamp}.wav"
            
#             with wave.open(file_name, "wb") as wf:
#                 wf.setnchannels(CHANNELS)
#                 wf.setsampwidth(SAMPLE_WIDTH)
#                 wf.setframerate(SAMPLE_RATE)
#                 wf.writeframes(final_audio.tobytes())
            
#             print(f"✅ Audio saved as {file_name} (Duration: {duration:.2f}s, RMS: {final_rms:.2f})")
#             self.reset()
#             return True
            
#         self.reset()
#         return False
    
#     def reset(self):
#         self.buffer = []
#         self.is_recording = False
#         self.silence_start = None
#         self.last_active_time = None
#         self.volume_window.clear()
#         self.valid_chunk_count = 0
#         self.recording_start_time = None

# # Create audio buffer instance
# audio_buffer = AudioBuffer()

# @sio.event
# def connect(sid, environ):
#     print(f"✅ Client {sid} connected")

# @sio.event
# def audio_chunk(sid, data):
#     """Handles incoming audio chunks and detects silence."""
#     audio_array = np.frombuffer(data, dtype=np.int16)
#     if audio_buffer.add_chunk(audio_array):
#         print(f"🎤 Finished recording from {sid}")

# @sio.event
# def disconnect(sid):
#     print(f"❌ Client {sid} disconnected")
#     if audio_buffer.buffer:
#         audio_buffer.save_buffer()

# if __name__ == "__main__":
#     print("🎤 Starting server on port 5000...")
#     eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)
#-----------------------------------------BEST(starting missing one letter)------------------------------------------------

#-----------------------------------------BEST(pre buffer logic)------------------------------------------------
# import socketio
# import eventlet
# import numpy as np
# import wave
# import time
# from datetime import datetime
# import os
# from collections import deque

# # Initialize Socket.IO server
# sio = socketio.Server(cors_allowed_origins="*")
# app = socketio.WSGIApp(sio)

# # Audio settings
# SAMPLE_RATE = 16000  # Hz
# CHANNELS = 1
# SAMPLE_WIDTH = 2  # 16-bit audio
# SAVE_DIR = "audio_files"

# # Ensure save directory exists
# os.makedirs(SAVE_DIR, exist_ok=True)

# # Audio detection settings
# SILENCE_THRESHOLD = 800  # Slightly reduced for better initial detection
# SILENCE_DURATION = 2.0  # Seconds of silence before saving
# MIN_AUDIO_DURATION = 2.0  # Minimum duration for saved audio
# MAX_AUDIO_DURATION = 30.0  # Maximum duration for saved audio
# CHUNK_DURATION = 0.064  # Duration of each chunk (1024 samples at 16kHz)
# MIN_VALID_CHUNKS = 3  # Minimum number of valid chunks required
# PRE_BUFFER_DURATION = 0.5  # Duration in seconds to keep before speech detection

# class AudioBuffer:
#     def __init__(self):
#         self.buffer = []
#         self.pre_buffer = deque(maxlen=int(PRE_BUFFER_DURATION / CHUNK_DURATION))
#         self.is_recording = False
#         self.silence_start = None
#         self.last_active_time = None
#         self.volume_window = deque(maxlen=int(0.3 / CHUNK_DURATION))  # 300ms window for faster response
#         self.valid_chunk_count = 0
#         self.recording_start_time = None
        
#     def calculate_rms(self, audio_array):
#         """Safely calculate RMS value with handling for empty or invalid arrays."""
#         if len(audio_array) == 0:
#             return 0.0
#         audio_float = audio_array.astype(np.float64)
#         squared = np.square(audio_float)
#         mean_squared = np.mean(squared)
#         if mean_squared < 0:
#             return 0.0
#         return np.sqrt(mean_squared)
        
#     def add_chunk(self, audio_array):
#         current_time = time.time()
        
#         # Calculate volume using safe RMS calculation
#         volume_rms = self.calculate_rms(audio_array)
#         self.volume_window.append(volume_rms)
        
#         # More responsive volume detection with lower lag
#         avg_volume = np.mean(list(self.volume_window)) if self.volume_window else 0
#         is_silent = avg_volume < SILENCE_THRESHOLD
        
#         if not self.is_recording:
#             # Keep filling pre-buffer when not recording
#             self.pre_buffer.append(audio_array)
        
#         # Start recording if we detect significant sound
#         if not is_silent:
#             if not self.is_recording:
#                 self.is_recording = True
#                 self.recording_start_time = current_time
#                 self.valid_chunk_count = 0
#                 # Add pre-buffer content to the main buffer
#                 self.buffer.extend(list(self.pre_buffer))
            
#             self.last_active_time = current_time
#             self.buffer.append(audio_array)
#             self.valid_chunk_count += 1
#             self.silence_start = None
#         else:
#             if self.is_recording:
#                 if self.silence_start is None:
#                     self.silence_start = current_time
#                 self.buffer.append(audio_array)
                
#                 # Check conditions for saving
#                 silence_duration = current_time - self.silence_start
#                 total_duration = current_time - self.recording_start_time
                
#                 if silence_duration >= SILENCE_DURATION:
#                     return self.save_buffer()
#                 elif total_duration >= MAX_AUDIO_DURATION:
#                     return self.save_buffer()
        
#         return False
    
#     def save_buffer(self):
#         if not self.buffer or self.valid_chunk_count < MIN_VALID_CHUNKS:
#             self.reset()
#             return False
            
#         # Calculate audio duration
#         total_samples = sum(len(chunk) for chunk in self.buffer)
#         duration = total_samples / SAMPLE_RATE
        
#         # Only save if duration meets requirements
#         if MIN_AUDIO_DURATION <= duration <= MAX_AUDIO_DURATION:
#             # Trim excess silence from the end
#             if self.silence_start and self.last_active_time:
#                 keep_duration = (self.last_active_time - self.recording_start_time) + 0.5
#                 keep_samples = int(keep_duration * SAMPLE_RATE)
                
#                 trimmed_buffer = []
#                 accumulated_samples = 0
                
#                 for chunk in self.buffer:
#                     if accumulated_samples + len(chunk) <= keep_samples:
#                         trimmed_buffer.append(chunk)
#                         accumulated_samples += len(chunk)
#                     else:
#                         remaining = keep_samples - accumulated_samples
#                         if remaining > 0:
#                             trimmed_buffer.append(chunk[:remaining])
#                         break
                
#                 final_audio = np.concatenate(trimmed_buffer, axis=0)
#             else:
#                 final_audio = np.concatenate(self.buffer, axis=0)
            
#             # Additional noise check on final audio
#             final_rms = self.calculate_rms(final_audio)
#             if final_rms < SILENCE_THRESHOLD:
#                 self.reset()
#                 return False
            
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
#             file_name = f"{SAVE_DIR}/audio_{timestamp}.wav"
            
#             with wave.open(file_name, "wb") as wf:
#                 wf.setnchannels(CHANNELS)
#                 wf.setsampwidth(SAMPLE_WIDTH)
#                 wf.setframerate(SAMPLE_RATE)
#                 wf.writeframes(final_audio.tobytes())
            
#             print(f"✅ Audio saved as {file_name} (Duration: {duration:.2f}s, RMS: {final_rms:.2f})")
#             self.reset()
#             return True
            
#         self.reset()
#         return False
    
#     def reset(self):
#         self.buffer = []
#         self.is_recording = False
#         self.silence_start = None
#         self.last_active_time = None
#         self.volume_window.clear()
#         self.valid_chunk_count = 0
#         self.recording_start_time = None
#         # Keep pre-buffer intact

# # Create audio buffer instance
# audio_buffer = AudioBuffer()

# @sio.event
# def connect(sid, environ):
#     print(f"✅ Client {sid} connected")

# @sio.event
# def audio_chunk(sid, data):
#     """Handles incoming audio chunks and detects silence."""
#     audio_array = np.frombuffer(data, dtype=np.int16)
#     if audio_buffer.add_chunk(audio_array):
#         print(f"🎤 Finished recording from {sid}")

# @sio.event
# def disconnect(sid):
#     print(f"❌ Client {sid} disconnected")
#     if audio_buffer.buffer:
#         audio_buffer.save_buffer()

# if __name__ == "__main__":
#     print("🎤 Starting server on port 5000...")
#     eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)
#-----------------------------------------BEST(pre buffer logic)------------------------------------------------




import socketio
import eventlet
import numpy as np
import wave
import time
from datetime import datetime
import os
from collections import deque
import requests
import json
import soundfile as sf
#from pydub import AudioSegment
#from pydub.playback import play
from playsound import playsound
from dotenv import load_dotenv
load_dotenv()
# Initialize Socket.IO server
sio = socketio.Server(cors_allowed_origins="*")
app = socketio.WSGIApp(sio)

# Audio settings
SAMPLE_RATE = 16000  # Hz
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit audio
SAVE_DIR = "audio_files"



# API settings
TRANSCRIPTION_API_URL = os.getenv("TRANSCRIPTION_API_URL")
RAG_API_URL = os.getenv("RAG_API_URL")
TTS_API_URL = os.getenv("TTS_API_URL")
# Ensure save directory exists
os.makedirs(SAVE_DIR, exist_ok=True)

# Audio detection settings
SILENCE_THRESHOLD = 700 # 800
SILENCE_DURATION = 2.0
MIN_AUDIO_DURATION = 0.1 # 3
MAX_AUDIO_DURATION = 30.0
CHUNK_DURATION = 0.064 #0.064
MIN_VALID_CHUNKS = 2 #3
PRE_BUFFER_DURATION = 0.32 #0.5

def send_to_speech_api(file_path):
    """Send audio file to speech-to-text API and return transcription."""
    try:
        with open(file_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            response = requests.post(TRANSCRIPTION_API_URL, files=files)
            
            if response.status_code == 200:
                result = response.json()
                transcription = result.get('answer', '')
                print(f"🔊 Transcription: {transcription}")
                #os.remove(file_path)
                return transcription
            else:
                print(f"❌ API Error: Status code {response.status_code}")
                return None
    except Exception as e:
        print(f"❌ Error sending to API: {str(e)}")
        return None
    
def send_to_rag_api(transcription):
    try:
        payload = {"question": transcription}
        response = requests.post(RAG_API_URL, json=payload)
            
        if response.status_code == 200:
            result = response.json()
            answer = result.get('answer', '')
            return answer
        else:
            print(f"❌ API Error: Status code {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error sending to API: {str(e)}")
        return None

def send_to_tts_api(text):
    try:
        payload = {"text": text}
        response = requests.post(TTS_API_URL, json=payload)
            
        if response.status_code == 200:
            result = response.json()
            download_url = result.get('download_url', '')
            return download_url
        else:
            print(f"❌ API Error: Status code {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error sending to API: {str(e)}")
        return None

class AudioBuffer:
    def __init__(self):
        self.buffer = []
        self.pre_buffer = deque(maxlen=int(PRE_BUFFER_DURATION / CHUNK_DURATION))
        self.is_recording = False
        self.silence_start = None
        self.last_active_time = None
        self.volume_window = deque(maxlen=int(0.5 / CHUNK_DURATION)) # 0.3
        self.valid_chunk_count = 0
        self.recording_start_time = None
        
    def calculate_rms(self, audio_array):
        if len(audio_array) == 0:
            return 0.0
        audio_float = audio_array.astype(np.float64)
        squared = np.square(audio_float)
        mean_squared = np.mean(squared)
        if mean_squared < 0:
            return 0.0
        return np.sqrt(mean_squared)
        
    def add_chunk(self, audio_array):
        current_time = time.time()
        
        volume_rms = self.calculate_rms(audio_array)
        self.volume_window.append(volume_rms)
        
        avg_volume = np.mean(list(self.volume_window)) if self.volume_window else 0
        is_silent = avg_volume < SILENCE_THRESHOLD
        
        if not self.is_recording:
            self.pre_buffer.append(audio_array)
        
        if not is_silent:
            if not self.is_recording:
                self.is_recording = True
                self.recording_start_time = current_time
                self.valid_chunk_count = 0
                self.buffer.extend(list(self.pre_buffer))
            
            self.last_active_time = current_time
            self.buffer.append(audio_array)
            self.valid_chunk_count += 1
            self.silence_start = None
        else:
            if self.is_recording:
                if self.silence_start is None:
                    self.silence_start = current_time
                self.buffer.append(audio_array)
                
                silence_duration = current_time - self.silence_start
                total_duration = current_time - self.recording_start_time
                
                if silence_duration >= SILENCE_DURATION:
                    return self.save_buffer()
                elif total_duration >= MAX_AUDIO_DURATION:
                    return self.save_buffer()
        
        return False
    
    def save_buffer(self):
        if not self.buffer or self.valid_chunk_count < MIN_VALID_CHUNKS:
            self.reset()
            return False
            
        total_samples = sum(len(chunk) for chunk in self.buffer)
        duration = total_samples / SAMPLE_RATE
        
        if MIN_AUDIO_DURATION <= duration <= MAX_AUDIO_DURATION:
            if self.silence_start and self.last_active_time:
                keep_duration = (self.last_active_time - self.recording_start_time) + 0.5
                keep_samples = int(keep_duration * SAMPLE_RATE)
                
                trimmed_buffer = []
                accumulated_samples = 0
                
                for chunk in self.buffer:
                    if accumulated_samples + len(chunk) <= keep_samples:
                        trimmed_buffer.append(chunk)
                        accumulated_samples += len(chunk)
                    else:
                        remaining = keep_samples - accumulated_samples
                        if remaining > 0:
                            trimmed_buffer.append(chunk[:remaining])
                        break
                
                final_audio = np.concatenate(trimmed_buffer, axis=0)
            else:
                final_audio = np.concatenate(self.buffer, axis=0)
            
            final_rms = self.calculate_rms(final_audio)
            if final_rms < SILENCE_THRESHOLD:
                self.reset()
                return False
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            file_name = f"{SAVE_DIR}/audio_{timestamp}.wav"
            
            with wave.open(file_name, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(SAMPLE_WIDTH)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(final_audio.tobytes())
            
            print(f"✅ Audio saved as {file_name} (Duration: {duration:.2f}s, RMS: {final_rms:.2f})")
            t_start=time.time()
            # Send the saved file to speech-to-text API
            transcription = send_to_speech_api(file_name)
            if transcription:
                print(f"📝 Transcription received: {transcription}")
                answer = send_to_rag_api(transcription)
                if answer:
                    print(answer)
                    download_url = send_to_tts_api(answer)
                    if download_url:
                        file_name = os.path.basename(download_url)
                        audio_response = requests.get(download_url)
                        if audio_response.status_code == 200:
                            with open(file_name, "wb") as file:
                                file.write(audio_response.content)
                            print(f"Audio file saved as: {file_name}")
                            # audio = AudioSegment.from_file(file_name)
                            # play(audio)
                            t_end=time.time()
                            t_taken = t_end-t_start
                            print("✅Time taken:",t_taken)
                            #playsound(file_name)

                        else:
                            print("❌ Failed to download audio file")
                    else:
                        print("❌ Download URL not found in response")
                else:
                    print("❌ Answer not found from LLM response")
            else:
                print("❌ Error Generating Transcription")
            self.reset()
            return True
            
        self.reset()
        return False
    
    def reset(self):
        self.buffer = []
        self.is_recording = False
        self.silence_start = None
        self.last_active_time = None
        self.volume_window.clear()
        self.valid_chunk_count = 0
        self.recording_start_time = None

# Create audio buffer instance
audio_buffer = AudioBuffer()

@sio.event
def connect(sid, environ):
    print(f"✅ Client {sid} connected")

@sio.event
def audio_chunk(sid, data):
    """Handles incoming audio chunks and detects silence."""
    audio_array = np.frombuffer(data, dtype=np.int16)
    if audio_buffer.add_chunk(audio_array):
        print(f"🎤 Finished recording from {sid}")

@sio.event
def disconnect(sid):
    print(f"❌ Client {sid} disconnected")
    if audio_buffer.buffer:
        audio_buffer.save_buffer()

if __name__ == "__main__":
    print("🎤 Starting server on port 5000...")
    eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)