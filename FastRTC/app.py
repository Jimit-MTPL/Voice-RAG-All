from fastrtc import (
    ReplyOnPause, AdditionalOutputs, Stream,
    audio_to_bytes, aggregate_bytes_to_16bit
)
import gradio as gr
from groq import Groq
import anthropic
from elevenlabs import ElevenLabs

groq_client = Groq()
claude_client = anthropic.Anthropic()
tts_client = ElevenLabs()


# See "Talk to Claude" in Cookbook for an example of how to keep 
# track of the chat history.
def response(
    audio: tuple[int, np.ndarray],
):
    prompt = groq_client.audio.transcriptions.create(
        file=("audio-file.mp3", audio_to_bytes(audio)),
        model="whisper-large-v3-turbo",
        response_format="verbose_json",
    ).text
    response = claude_client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = " ".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    )
    iterator = tts_client.text_to_speech.convert_as_stream(
        text=response_text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_multilingual_v2",
        output_format="pcm_24000"
        
    )
    for chunk in aggregate_bytes_to_16bit(iterator):
        audio_array = np.frombuffer(chunk, dtype=np.int16).reshape(1, -1)
        yield (24000, audio_array)

stream = Stream(
    modality="audio",
    mode="send-receive",
    handler=ReplyOnPause(response),
)


import os

from fastrtc import (ReplyOnPause, Stream, get_stt_model, get_tts_model)
from openai import OpenAI

sambanova_client = OpenAI(
    api_key=os.getenv("SAMBANOVA_API_KEY"), base_url="https://api.sambanova.ai/v1"
)
stt_model = get_stt_model()
tts_model = get_tts_model()

def echo(audio):
    prompt = stt_model.stt(audio)
    response = sambanova_client.chat.completions.create(
        model="Meta-Llama-3.2-3B-Instruct",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
    )
    prompt = response.choices[0].message.content
    for audio_chunk in tts_model.stream_tts_sync(prompt):
        yield audio_chunk

stream = Stream(ReplyOnPause(echo), modality="audio", mode="send-receive")