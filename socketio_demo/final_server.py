import socketio
import eventlet
import numpy as np
import wave
import time
import os
from collections import deque
import requests
from dotenv import load_dotenv
load_dotenv()

sio = socketio.Server(cors_allowed_origins="*")
app = socketio.WSGIApp(sio)

# Audio settings
SAMPLE_RATE = 16000  # Hz
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit audio

# API settings
TRANSCRIPTION_API_URL = os.getenv("TRANSCRIPTION_API_URL")
RAG_API_URL = os.getenv("RAG_API_URL")
TTS_API_URL = os.getenv("TTS_API_URL")

# Audio detection settings
SILENCE_THRESHOLD = 550
SILENCE_DURATION = 1.2
MIN_AUDIO_DURATION = 1
MAX_AUDIO_DURATION = 30.0
CHUNK_DURATION = 0.064
MIN_VALID_CHUNKS = 2
PRE_BUFFER_DURATION = 0.5

# Add processing state tracking
processing_states = {}

def send_to_speech_api(file_path):
    """Send audio file to speech-to-text API and return transcription."""
    try:
        with open(file_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            response = requests.post(TRANSCRIPTION_API_URL, files=files)
            
            if response.status_code == 200:
                result = response.json()
                transcription = result.get('answer', '')
                print(f"🔊User: {transcription}")
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
        self.volume_window = deque(maxlen=int(0.5 / CHUNK_DURATION))
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
            # Only start recording if we detect non-silent audio
            if not is_silent:
                self.is_recording = True
                self.recording_start_time = current_time
                self.valid_chunk_count = 0
                self.buffer.extend(list(self.pre_buffer))
                self.last_active_time = current_time
            return False
        
        # We are recording
        self.buffer.append(audio_array)
        
        if not is_silent:
            self.last_active_time = current_time
            self.valid_chunk_count += 1
            self.silence_start = None
        else:
            if self.silence_start is None:
                self.silence_start = current_time
            
            silence_duration = current_time - self.silence_start if self.silence_start else 0
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
        
        # Calculate actual audio content
        audio_data = np.concatenate(self.buffer, axis=0)
        duration = len(audio_data) / SAMPLE_RATE
        
        if duration < MIN_AUDIO_DURATION:
            self.reset()
            return False
            
        if duration > MAX_AUDIO_DURATION:
            # Trim to maximum duration
            samples_to_keep = int(MAX_AUDIO_DURATION * SAMPLE_RATE)
            audio_data = audio_data[:samples_to_keep]
            
        # Verify the audio has actual content
        final_rms = self.calculate_rms(audio_data)
        if final_rms < SILENCE_THRESHOLD:
            self.reset()
            return False
            
        # Save the verified audio
        file_name = os.path.basename("audio_input.wav")
        
        with wave.open(file_name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())

        # Notify client & update state AFTER confirming valid audio
        sio.emit('processing_started', room=current_sid)
        processing_states[current_sid] = True

        transcription = send_to_speech_api(file_name)
        if transcription:
            sio.emit('transcription_received', transcription, room=current_sid)
            answer = send_to_rag_api(transcription)
            if answer:
                sio.emit('answer_received', answer, room=current_sid)
                print(f"Assistant:{answer}")
                download_url = send_to_tts_api(answer)
                if download_url:
                    sio.emit('download_url_received', download_url, room=current_sid)
                    processing_states[current_sid] = False
                else:
                    print("❌ Download URL not found in response")
                    sio.emit('processing_error', room=current_sid)
                    processing_states[current_sid] = False
            else:
                print("❌ Answer not found from LLM response")
                sio.emit('processing_error', room=current_sid)
                processing_states[current_sid] = False
        else:
            print("❌ Error Generating Transcription")
            sio.emit('processing_error', room=current_sid)
            processing_states[current_sid] = False
        self.reset()
        return True

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
current_sid = None

@sio.event
def connect(sid, environ):
    print(f"✅ Client {sid} connected")
    processing_states[sid] = False

@sio.event
def audio_chunk(sid, data):
    """Handles incoming audio chunks and detects silence."""
    global current_sid
    
    # Check if currently processing
    if processing_states.get(sid, False):
        return
    
    current_sid = sid
    audio_array = np.frombuffer(data, dtype=np.int16)
    if audio_buffer.add_chunk(audio_array):
        print(f"🎤 Finished audio processing from {sid}")

@sio.event
def disconnect(sid):
    print(f"❌ Client {sid} disconnected")
    if sid in processing_states:
        del processing_states[sid]
    if audio_buffer.buffer:
        audio_buffer.save_buffer()

if __name__ == "__main__":
    print("🎤 Starting server on port 5000...")
    eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 5000)), app)