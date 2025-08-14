# import os
# import numpy as np
# import wave
# import time
# import requests
# from datetime import datetime
# from dotenv import load_dotenv
# from aioquic.asyncio import serve
# from aioquic.quic.configuration import QuicConfiguration
# from aioquic.asyncio.webtransport import WebTransportSession
# from collections import deque

# load_dotenv()

# # API settings
# TRANSCRIPTION_API_URL = os.getenv("TRANSCRIPTION_API_URL")
# RAG_API_URL = os.getenv("RAG_API_URL")
# TTS_API_URL = os.getenv("TTS_API_URL")
# RESET_API_URL = os.getenv("RESET_URL")

# # Directories
# base_dir = os.path.dirname(os.path.abspath(__file__))
# OUTPUT_FOLDER = os.path.join(base_dir, "output_files")
# SAVE_DIR = os.path.join(base_dir, "input_files")
# os.makedirs(SAVE_DIR, exist_ok=True)

# # Audio settings
# SAMPLE_RATE = 16000
# CHANNELS = 1
# SAMPLE_WIDTH = 2

# # Silence detection
# SILENCE_THRESHOLD = 700
# SILENCE_DURATION = 1.2
# CHUNK_DURATION = 0.064

# # Processing state
# processing_states = {}

# class AudioBuffer:
#     def __init__(self, sid):
#         self.sid = sid
#         self.buffer = []
#         self.volume_window = deque(maxlen=int(0.5 / CHUNK_DURATION))
#         self.is_recording = False
#         self.last_active_time = None

#     def calculate_rms(self, audio_array):
#         if len(audio_array) == 0:
#             return 0.0
#         audio_float = audio_array.astype(np.float64)
#         return np.sqrt(np.mean(np.square(audio_float)))

#     def add_chunk(self, audio_array):
#         current_time = time.time()
#         volume_rms = self.calculate_rms(audio_array)
#         self.volume_window.append(volume_rms)
#         avg_volume = np.mean(list(self.volume_window))

#         is_silent = avg_volume < SILENCE_THRESHOLD

#         if not self.is_recording and not is_silent:
#             self.is_recording = True
#             self.buffer.clear()

#         if self.is_recording:
#             self.buffer.append(audio_array)
#             self.last_active_time = current_time if not is_silent else self.last_active_time

#             if time.time() - self.last_active_time > SILENCE_DURATION:
#                 self.save_buffer()
#                 self.reset()

#     def save_buffer(self):
#         if not self.buffer:
#             return

#         audio_data = np.concatenate(self.buffer, axis=0)
#         file_name = os.path.join(SAVE_DIR, f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")

#         with wave.open(file_name, "wb") as wf:
#             wf.setnchannels(CHANNELS)
#             wf.setsampwidth(SAMPLE_WIDTH)
#             wf.setframerate(SAMPLE_RATE)
#             wf.writeframes(audio_data.tobytes())

#         transcription = self.send_to_speech_api(file_name)
#         os.remove(file_name)
#         if transcription:
#             print(f"User({self.sid}): {transcription}")

#     def send_to_speech_api(self, file_path):
#         try:
#             with open(file_path, 'rb') as audio_file:
#                 response = requests.post(TRANSCRIPTION_API_URL, files={'audio': audio_file})
#                 return response.json().get('answer', '') if response.status_code == 200 else None
#         except Exception as e:
#             print(f"API Error: {e}")
#             return None

#     def reset(self):
#         self.buffer.clear()
#         self.is_recording = False
#         self.volume_window.clear()

# class WebTransportHandler:
#     def __init__(self):
#         self.sessions = {}

#     async def handle_session(self, session: WebTransportSession):
#         print(f"New session: {session.session_id}")
#         sid = session.session_id
#         self.sessions[sid] = AudioBuffer(sid)

#         async for stream in session.receive_bidirectional():
#             while True:
#                 data = await stream.read(4096)
#                 if not data:
#                     break
#                 audio_array = np.frombuffer(data, dtype=np.int16)
#                 self.sessions[sid].add_chunk(audio_array)

#         print(f"Session closed: {sid}")
#         if sid in self.sessions:
#             del self.sessions[sid]

# async def main():
#     configuration = QuicConfiguration(is_client=False)
#     configuration.load_cert_chain(certfile="cert.pem", keyfile="key.pem")

#     handler = WebTransportHandler()
#     await serve("0.0.0.0", 8504, configuration=configuration, create_protocol=handler.handle_session)

# if __name__ == "__main__":
#     import asyncio
#     print("Starting WebTransport server on port 8504...")
#     asyncio.run(main())

import asyncio
import numpy as np
import wave
import time
import os
from collections import deque
from datetime import datetime
import requests
from dotenv import load_dotenv
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.asyncio.server import serve
from aioquic.h3.connection import H3_ALPN
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.events import H3Event, DataReceived, WebTransportStreamDataReceived

load_dotenv()

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
OUTPUT_FOLDER = os.path.join(base_dir, "output_files")
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

# Processing state tracking
processing_states = {}

class AudioBuffer:
    def __init__(self, session_id, send_message):
        self.session_id = session_id
        self.send_message = send_message
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

    async def add_chunk(self, audio_array):
        current_time = time.time()

        volume_rms = self.calculate_rms(audio_array)
        self.volume_window.append(volume_rms)

        avg_volume = np.mean(list(self.volume_window)) if self.volume_window else 0
        is_silent = avg_volume < SILENCE_THRESHOLD

        if not self.is_recording:
            self.pre_buffer.append(audio_array)
            if not is_silent:
                self.is_recording = True
                self.recording_start_time = current_time
                self.valid_chunk_count = 0
                self.buffer.extend(list(self.pre_buffer))
                self.last_active_time = current_time
            return False

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
                return await self.save_buffer()
            elif total_duration >= MAX_AUDIO_DURATION:
                return await self.save_buffer()

        return False

    async def save_buffer(self):
        if not self.buffer or self.valid_chunk_count < MIN_VALID_CHUNKS:
            self.reset()
            return False

        audio_data = np.concatenate(self.buffer, axis=0)
        duration = len(audio_data) / SAMPLE_RATE

        if duration < MIN_AUDIO_DURATION:
            self.reset()
            return False

        if duration > MAX_AUDIO_DURATION:
            samples_to_keep = int(MAX_AUDIO_DURATION * SAMPLE_RATE)
            audio_data = audio_data[:samples_to_keep]

        final_rms = self.calculate_rms(audio_data)
        if final_rms < SILENCE_THRESHOLD:
            self.reset()
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_name = os.path.join(SAVE_DIR, f"audio_{timestamp}.wav")
        
        with wave.open(file_name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())

        processing_states[self.session_id] = True

        # Process the audio file
        transcription = await self.send_to_speech_api(file_name)
        os.remove(file_name)
        
        if transcription:
            await self.send_message({
                'type': 'transcription_received',
                'text': transcription
            })
            
            answer = await self.send_to_rag_api(transcription)
            if answer:
                await self.send_message({
                    'type': 'translation_received',
                    'text': answer
                })
                
                download_url = await self.send_to_tts_api(answer)
                if download_url:
                    file_name = os.path.basename(download_url)
                    file_path = os.path.join(OUTPUT_FOLDER, file_name)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(download_url) as response:
                            if response.status == 200:
                                content = await response.read()
                                with open(file_path, "wb") as file:
                                    file.write(content)
                                await self.send_message({
                                    'type': 'audio_ready',
                                    'file': file_name
                                })

        processing_states[self.session_id] = False
        self.reset()
        return True

    async def send_to_speech_api(self, file_path):
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as audio_file:
                data = aiohttp.FormData()
                data.add_field('audio', audio_file)
                async with session.post(TRANSCRIPTION_API_URL, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('answer', '')
        return None

    async def send_to_rag_api(self, transcription):
        async with aiohttp.ClientSession() as session:
            payload = {"question": transcription, "sid": self.session_id}
            async with session.post(RAG_API_URL, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('answer', '')
        return None

    async def send_to_tts_api(self, text):
        async with aiohttp.ClientSession() as session:
            payload = {"text": text}
            async with session.post(TTS_API_URL, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('download_url', '')
        return None

    def reset(self):
        self.buffer = []
        self.is_recording = False
        self.silence_start = None
        self.last_active_time = None
        self.volume_window.clear()
        self.valid_chunk_count = 0
        self.recording_start_time = None

class WebTransportProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = str(id(self))
        self.audio_buffer = None
        self._streams = {}

    def handle_event(self, event: H3Event) -> None:
        if isinstance(event, WebTransportStreamDataReceived):
            asyncio.create_task(self.handle_data(event.data, event.stream_id))

    async def handle_data(self, data: bytes, stream_id: int) -> None:
        if not self.audio_buffer:
            self.audio_buffer = AudioBuffer(
                self.session_id,
                lambda msg: self.send_message(msg, stream_id)
            )

        if processing_states.get(self.session_id, False):
            return

        audio_array = np.frombuffer(data, dtype=np.int16)
        await self.audio_buffer.add_chunk(audio_array)

    async def send_message(self, message: dict, stream_id: int) -> None:
        if stream_id not in self._streams:
            self._streams[stream_id] = self._quic.get_stream(stream_id)
        
        await self._streams[stream_id].send_data(
            json.dumps(message).encode(),
            end_stream=False
        )

async def main():
    configuration = QuicConfiguration(
        alpn_protocols=H3_ALPN,
        is_client=False,
        max_datagram_frame_size=65536,
    )
    
    # Load SSL certificate and private key
    configuration.load_cert_chain("cert.pem", "key.pem")

    await serve(
        host="0.0.0.0",
        port=8504,
        configuration=configuration,
        create_protocol=WebTransportProtocol,
    )
    
    print("WebTransport server running on port 8504...")
    await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass