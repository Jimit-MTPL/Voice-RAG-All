from fastrtc import Stream, ReplyOnPause, get_stt_model, get_tts_model
from groq import Groq
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize FastRTC STT and TTS models
stt_model = get_stt_model()
tts_model = get_tts_model()

# Define the response function
def respond(audio: tuple[int, np.ndarray]):
    # Transcribe audio to text
    text = stt_model.stt(audio)
    # Generate LLM response
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": text}],
        max_tokens=200,
    )
    response_text = response.choices[0].message.content
    # Convert text response to speech
    for audio_chunk in tts_model.stream_tts_sync(response_text):
        yield audio_chunk

# Set up the FastRTC stream
stream = Stream(
    handler=ReplyOnPause(respond),
    modality="audio",
    mode="send-receive"
)

# Launch the Gradio UI
stream.ui.launch(share=True)
