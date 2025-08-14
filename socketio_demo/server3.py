import socketio
import eventlet
import numpy as np
import wave
import time
from datetime import datetime
import os
from collections import deque
import requests
#import json
#import soundfile as sf
#from pydub import AudioSegment
#from pydub.playback import play
from playsound import playsound
from dotenv import load_dotenv
load_dotenv()

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
SILENCE_THRESHOLD = 600
SILENCE_DURATION = 2.0
MIN_AUDIO_DURATION = 0.5
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
                print(f"🔊 Transcription: {transcription}")
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
        
    # [Previous methods remain the same until save_buffer]
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
        
        # Step 1: Compute total samples and raw duration BEFORE trimming
        total_samples = sum(len(chunk) for chunk in self.buffer)
        raw_duration = total_samples / SAMPLE_RATE  # Duration before trimming
        
        # Step 2: Trim silence if necessary
        if self.silence_start and self.last_active_time:
            keep_duration = (self.last_active_time - self.recording_start_time) + 0.5  # Extra 0.5s buffer
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
            final_audio = np.concatenate(self.buffer, axis=0)  # Use full buffer if no trimming is needed

        # Step 3: Compute actual duration AFTER trimming
        final_duration = len(final_audio) / SAMPLE_RATE

        # Step 4: Validate Duration & Silence Threshold
        if not (MIN_AUDIO_DURATION <= final_duration <= MAX_AUDIO_DURATION):
            print(f"❌ Discarding audio (Invalid Duration: {final_duration:.2f}s)")
            self.reset()
            return False
        
        final_rms = self.calculate_rms(final_audio)
        if final_rms < SILENCE_THRESHOLD:
            print("❌ Detected silence. Discarding audio.")
            self.reset()
            return False

        # Step 5: Save Processed Audio to File
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_name = f"{SAVE_DIR}/audio_{timestamp}.wav"
        
        with wave.open(file_name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(final_audio.tobytes())

        print(f"✅ Audio saved as {file_name} (Final Duration: {final_duration:.2f}s)")
        
        # Step 6: Start Processing
        t_start = time.time()

        # Notify client & update state AFTER confirming valid audio
        sio.emit('processing_started', room=current_sid)
        processing_states[current_sid] = True

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
                        t_end = time.time()
                        t_taken = t_end - t_start
                        print("✅ Time taken:", t_taken)
                        playsound(file_name)

                        # Notify client of completion
                        sio.emit('processing_complete', room=current_sid)
                        processing_states[current_sid] = False
                    else:
                        print("❌ Failed to download audio file")
                        sio.emit('processing_error', room=current_sid)
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
    # def save_buffer(self):
    #     if not self.buffer or self.valid_chunk_count < MIN_VALID_CHUNKS:
    #         self.reset()
    #         return False
        
    #     total_samples = sum(len(chunk) for chunk in self.buffer)
    #     duration = total_samples / SAMPLE_RATE
        
    #     if MIN_AUDIO_DURATION <= duration <= MAX_AUDIO_DURATION:
    #         # [Previous audio processing code remains the same until API calls]
    #         if self.silence_start and self.last_active_time:
    #             keep_duration = (self.last_active_time - self.recording_start_time) + 0.5
    #             keep_samples = int(keep_duration * SAMPLE_RATE)
                
    #             trimmed_buffer = []
    #             accumulated_samples = 0
                
    #             for chunk in self.buffer:
    #                 if accumulated_samples + len(chunk) <= keep_samples:
    #                     trimmed_buffer.append(chunk)
    #                     accumulated_samples += len(chunk)
    #                 else:
    #                     remaining = keep_samples - accumulated_samples
    #                     if remaining > 0:
    #                         trimmed_buffer.append(chunk[:remaining])
    #                     break
                
    #             final_audio = np.concatenate(trimmed_buffer, axis=0)
    #         else:
    #             final_audio = np.concatenate(self.buffer, axis=0)
            
    #         final_rms = self.calculate_rms(final_audio)
    #         if final_rms < SILENCE_THRESHOLD:
    #             self.reset()
    #             return False
    #         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    #         file_name = f"{SAVE_DIR}/audio_{timestamp}.wav"
            
    #         with wave.open(file_name, "wb") as wf:
    #             wf.setnchannels(CHANNELS)
    #             wf.setsampwidth(SAMPLE_WIDTH)
    #             wf.setframerate(SAMPLE_RATE)
    #             wf.writeframes(final_audio.tobytes())
            
    #         print(f"✅ Audio saved as {file_name} (Duration: {duration:.2f}s)")
    #         t_start = time.time()
            
    #         # Notify client that processing is starting
    #         sio.emit('processing_started', room=current_sid)
    #         processing_states[current_sid] = True
            
    #         # Process the audio
    #         transcription = send_to_speech_api(file_name)
    #         if transcription:
    #             print(f"📝 Transcription received: {transcription}")
    #             answer = send_to_rag_api(transcription)
    #             if answer:
    #                 print(answer)
    #                 download_url = send_to_tts_api(answer)
    #                 if download_url:
    #                     file_name = os.path.basename(download_url)
    #                     audio_response = requests.get(download_url)
    #                     if audio_response.status_code == 200:
    #                         with open(file_name, "wb") as file:
    #                             file.write(audio_response.content)
    #                         t_end = time.time()
    #                         t_taken = t_end - t_start
    #                         print("✅ Time taken:", t_taken)
    #                         playsound(file_name)
    #                         # Notify client that processing is complete
    #                         sio.emit('processing_complete', room=current_sid)
    #                         processing_states[current_sid] = False
    #                     else:
    #                         print("❌ Failed to download audio file")
    #                         sio.emit('processing_error', room=current_sid)
    #                         processing_states[current_sid] = False
    #                 else:
    #                     print("❌ Download URL not found in response")
    #                     sio.emit('processing_error', room=current_sid)
    #                     processing_states[current_sid] = False
    #             else:
    #                 print("❌ Answer not found from LLM response")
    #                 sio.emit('processing_error', room=current_sid)
    #                 processing_states[current_sid] = False
                    
    #         else:
    #             print("❌ Error Generating Transcription")
    #             sio.emit('processing_error', room=current_sid)
    #             processing_states[current_sid] = False
            
    #         self.reset()
    #         return True
            
    #     self.reset()
    #     return False
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
        print(f"🎤 Finished recording from {sid}")

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