import eventlet
eventlet.monkey_patch()

# Now import other modules
import socketio
import numpy as np
import wave
import time
import os
import asyncio
import concurrent.futures
from collections import deque
from datetime import datetime
import requests
from dotenv import load_dotenv
import io
import wave
import time
load_dotenv()

sio = socketio.Server(cors_allowed_origins='*', async_mode='eventlet')
app = socketio.WSGIApp(sio)

# Create a session for persistent connections
session = requests.Session()

# Thread pool for parallel processing
# executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

# Audio settings
SAMPLE_RATE = 16000  # Hz
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit audio

# API settings
TRANSCRIPTION_API_URL = os.getenv("TRANSCRIPTION_API_URL")
RAG_API_URL = os.getenv("RAG_API_URL")
TTS_API_URL = os.getenv("TTS_API_URL")
RESET_API_URL = os.getenv("RESET_URL")
base_dir = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FOLER = os.path.join(base_dir, "output_files")
SAVE_DIR = os.path.join(base_dir, "input_files")
os.makedirs(SAVE_DIR, exist_ok=True)
# Audio detection settings
SILENCE_THRESHOLD = 700
SILENCE_DURATION = 1.2
MIN_AUDIO_DURATION = 1
MAX_AUDIO_DURATION = 30.0
CHUNK_DURATION = 0.064
MIN_VALID_CHUNKS = 2
PRE_BUFFER_DURATION = 0.5

# Add processing state tracking
processing_states = {}

class SessionState:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.tts_start_time = None
        self.tts_end_time = None
session_state = SessionState()
def send_to_speech_api(temp_audio_input):
    """Send audio file to speech-to-text API and return transcription."""
    try:
        files = {'audio': ('audio.wav', temp_audio_input, 'audio/wav')}
        response = session.post(TRANSCRIPTION_API_URL, files=files)

        if response.status_code == 200:
            result = response.json()
            transcription = result.get('answer', '')
            print(f"User: {transcription}")
            return transcription
        else:
            print(f"API Error: Status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error sending to API: {str(e)}")
        return None
    # try:
    #     with open(file_path, 'rb') as audio_file:
    #         files = {'audio': audio_file}
    #         response = session.post(TRANSCRIPTION_API_URL, files=files)

    #         if response.status_code == 200:
    #             result = response.json()
    #             transcription = result.get('answer', '')
    #             print(f"User: {transcription}")
    #             return transcription
    #         else:
    #             print(f"API Error: Status code {response.status_code}")
    #             return None
    # except Exception as e:
    #     print(f"Error sending to API: {str(e)}")
    #     return None


def send_to_rag_api(transcription, sid):
    try:
        payload = {"question": transcription, "sid": sid}
        response = session.post(RAG_API_URL, json=payload)

        if response.status_code == 200:
            result = response.json()
            answer = result.get('answer', '')
            return answer
        else:
            print(f"API Error: Status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error sending to API: {str(e)}")
        return None


def send_to_tts_api(text):
    try:
        payload = {"text": text}
        response = session.post(TTS_API_URL, json=payload)

        if response.status_code == 200:
            result = response.json()
            download_url = result.get('download_url', '')
            return download_url
        else:
            print(f"API Error: Status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error sending to API: {str(e)}")
        return None


def download_audio_file(download_url, sid):
    try:
        file_name = os.path.basename(download_url)
        file_path = os.path.join(OUTPUT_FOLER, file_name)
        audio_response = session.get(download_url)
        if audio_response.status_code == 200:
            with open(file_path, "wb") as file:
                file.write(audio_response.content)
            return file_name
        else:
            print(f"Error downloading audio: Status code {audio_response.status_code}")
            return None
    except Exception as e:
        print(f"Error downloading audio: {str(e)}")
        return None


def process_audio_parallel(temp_audio_input, sid):
    """Process audio using parallel execution for APIs."""
    try:
        # Use eventlet green threads for concurrency instead of asyncio
        # Step 1: Transcription
        transcription = send_to_speech_api(temp_audio_input)
        
        if not transcription:
            print("Error Generating Transcription")
            processing_states[sid] = False
            return
        
        # Send transcription to user immediately
        sio.emit('transcription_received', {'text': transcription}, room=sid)
        session_state.end_time = time.time()
        time_taken=session_state.end_time-session_state.start_time
        print(f"-----------time taken:{time_taken}-----------")
        # Step 2: RAG processing - start in a green thread
        def rag_task():
            answer = send_to_rag_api(transcription, sid)
            if answer:
                sio.emit('translation_received', {'text': answer}, room=sid)
                session_state.tts_start_time = time.time()
                # Step 3: Text-to-Speech - start in another green thread
                def tts_task():
                    download_url = send_to_tts_api(answer)
                    if download_url:
                        file_name = download_audio_file(download_url, sid)
                        if file_name:
                            sio.emit('audio_ready', {'file': file_name}, room=sid)
                            session_state.tts_end_time = time.time()
                            tts_time_taken = session_state.tts_end_time - session_state.tts_start_time 
                            print(f"-----------tts time taken:{tts_time_taken}-----------")
                    processing_states[sid] = False
                
                eventlet.spawn(tts_task)
            else:
                print("Answer not found from LLM response")
                processing_states[sid] = False
        
        eventlet.spawn(rag_task)
        
    except Exception as e:
        print(f"Error in parallel processing: {str(e)}")
        processing_states[sid] = False


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

        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # file_name = os.path.join(SAVE_DIR, f"audio_{timestamp}.wav")
        # with wave.open(file_name, "wb") as wf:
        #     wf.setnchannels(CHANNELS)
        #     wf.setsampwidth(SAMPLE_WIDTH)
        #     wf.setframerate(SAMPLE_RATE)
        #     wf.writeframes(audio_data.tobytes())
        temp_audio_buffer = io.BytesIO()
        session_state.start_time=time.time()
        with wave.open(temp_audio_buffer, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        temp_audio_buffer.seek(0)
        processing_states[current_sid] = True
        
        # Start parallel processing using eventlet
        eventlet.spawn(process_audio_parallel, temp_audio_buffer, current_sid)
        
        # Delete the temporary audio file after a delay (allowing time for processing)
        # def remove_file():
        #     eventlet.sleep(5)  # Give time for file to be processed
        #     try:
        #         os.remove(file_name)
        #         print(f"Removed temporary file: {file_name}")
        #     except Exception as e:
        #         print(f"Error removing file: {str(e)}")
        
        # eventlet.spawn(remove_file)
        
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
    print(f"Client {sid} connected")
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
    print(f"Client {sid} disconnected")
    
    # Use session for reset API call
    reset_url = RESET_API_URL
    payload = {"sid": sid}
    session.post(reset_url, json=payload)
    print(f"Reset request sent for sid: {sid}")
    
    if sid in processing_states:
        del processing_states[sid]
    if audio_buffer.buffer:
        audio_buffer.save_buffer()


if __name__ == "__main__":
    print("Starting server on port 8504...")
    eventlet.wsgi.server(eventlet.listen(("0.0.0.0", 8504)), app, log_output=False)