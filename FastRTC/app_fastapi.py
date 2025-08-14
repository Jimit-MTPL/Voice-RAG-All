# from fastrtc import Stream, ReplyOnPause, get_stt_model, get_tts_model
# from groq import Groq
# import numpy as np
# import os
# from dotenv import load_dotenv
# from fastapi import FastAPI
# import uvicorn

# load_dotenv()
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# # Initialize Groq client
# groq_client = Groq(api_key=GROQ_API_KEY)

# # Initialize FastRTC STT and TTS models
# stt_model = get_stt_model()
# tts_model = get_tts_model()

# # Define the response function
# def respond(audio: tuple[int, np.ndarray]):
#     # Transcribe audio to text
#     text = stt_model.stt(audio)
#     # Generate LLM response
#     response = groq_client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=[{"role": "user", "content": text}],
#         max_tokens=200,
#     )
#     response_text = response.choices[0].message.content
#     # Convert text response to speech
#     for audio_chunk in tts_model.stream_tts_sync(response_text):
#         yield audio_chunk

# # Set up the FastRTC stream
# stream = Stream(
#     handler=ReplyOnPause(respond),
#     modality="audio",
#     mode="send-receive"
# )

# # Create a FastAPI app
# app = FastAPI()

# # Mount the FastRTC stream onto the FastAPI app
# stream.mount(app)

# # Run the FastAPI app with Uvicorn
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)


import json
import os
import time
from pathlib import Path
import gradio as gr
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastrtc import (
    AdditionalOutputs,
    ReplyOnPause,
    Stream,
    get_tts_model,
    get_stt_model,
    get_twilio_turn_credentials,
)
from fastrtc.utils import audio_to_bytes
from gradio.utils import get_space
from groq import Groq
from pydantic import BaseModel
import requests
load_dotenv()

#claude_client = anthropic.Anthropic()
#tts_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RAG_API_URL = os.getenv("RAG_API_URL")
TEMP_RAG_API_URL = os.getenv("TEMP_RAG_API_URL")
# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)
curr_dir = Path(__file__).parent

tts_model = get_tts_model()
stt_model = get_stt_model()

def response(
    audio: tuple[int, np.ndarray],
    chatbot: list[dict] | None = None,
):
    chatbot = chatbot or []
    messages = [{"role": d["role"], "content": d["content"]} for d in chatbot]
    # prompt = groq_client.audio.transcriptions.create(
    #     file=("audio-file.mp3", audio_to_bytes(audio)),
    #     model="whisper-large-v3-turbo",
    #     response_format="verbose_json",
    # ).text
    prompt = stt_model.stt(audio)
    print("----------------------------------input----------------------------------")
    print(prompt)
    chatbot.append({"role": "user", "content": prompt})
    yield AdditionalOutputs(chatbot)
    messages.append({"role": "user", "content": prompt})
    # response = claude_client.messages.create(
    #     model="claude-3-5-haiku-20241022",
    #     max_tokens=512,
    #     messages=messages,  # type: ignore
    # )

    # response = groq_client.chat.completions.create(
    #     model="llama-3.3-70b-versatile",
    #     messages=messages,
    #     max_tokens=512,
    # )
    # response_text = response.choices[0].message.content
    # print("----------------------------------output----------------------------------")
    # print(prompt)
    response_text=""
    payload = {"question": prompt, "sid": "123456"}
    api_response = requests.post(TEMP_RAG_API_URL, json=payload)
    if api_response.status_code == 200:
        result = api_response.json()
        response_text = result.get('answer', '')
    else:
        print(f"API Error: Status code {api_response.status_code}")
    # response_text = " ".join(
    #     block.text  # type: ignore
    #     for block in response.content
    #     if getattr(block, "type", None) == "text"
    # )
    chatbot.append({"role": "assistant", "content": response_text})

    start = time.time()

    print("starting tts", start)
    for i, chunk in enumerate(tts_model.stream_tts_sync(response_text)):
        print("chunk", i, time.time() - start)
        yield chunk
        print("finished tts", time.time() - start)
        yield AdditionalOutputs(chatbot)


chatbot = gr.Chatbot(type="messages")
stream = Stream(
    modality="audio",
    mode="send-receive",
    handler=ReplyOnPause(response),
    additional_outputs_handler=lambda a, b: b,
    additional_inputs=[chatbot],
    additional_outputs=[chatbot],
    rtc_configuration=get_twilio_turn_credentials() if get_space() else None,
    concurrency_limit=5 if get_space() else None,
    time_limit=90 if get_space() else None,
)


class Message(BaseModel):
    role: str
    content: str


class InputData(BaseModel):
    webrtc_id: str
    chatbot: list[Message]


app = FastAPI()
stream.mount(app)


@app.get("/")
async def _():
    rtc_config = get_twilio_turn_credentials() if get_space() else None
    html_content = (curr_dir / "index.html").read_text()
    html_content = html_content.replace("__RTC_CONFIGURATION__", json.dumps(rtc_config))
    return HTMLResponse(content=html_content, status_code=200)


@app.post("/input_hook")
async def _(body: InputData):
    stream.set_input(body.webrtc_id, body.model_dump()["chatbot"])
    return {"status": "ok"}


@app.get("/outputs")
def _(webrtc_id: str):
    async def output_stream():
        async for output in stream.output_stream(webrtc_id):
            chatbot = output.args[0]
            yield f"event: output\ndata: {json.dumps(chatbot[-1])}\n\n"

    return StreamingResponse(output_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import os

    if (mode := os.getenv("MODE")) == "UI":
        stream.ui.launch(server_port=7860, server_name="0.0.0.0")
    elif mode == "PHONE":
        stream.fastphone(host="0.0.0.0", port=7860)
    else:
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=7860)


# https://beta15.moontechnolabs.com/rag-app/upload
# https://beta15.moontechnolabs.com/rag-app/ask


# from fastrtc import Stream, ReplyOnPause, get_stt_model, get_tts_model
# from groq import Groq
# import numpy as np
# import os
# from dotenv import load_dotenv
# from fastapi import FastAPI
# import uvicorn

# load_dotenv()
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# # Initialize Groq client
# groq_client = Groq(api_key=GROQ_API_KEY)

# # Initialize FastRTC STT and TTS models
# stt_model = get_stt_model()
# tts_model = get_tts_model()

# # Define the response function
# def respond(audio: tuple[int, np.ndarray]):
#     # Transcribe audio to text
#     text = stt_model.stt(audio)
#     # Generate LLM response
#     response = groq_client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=[{"role": "user", "content": text}],
#         max_tokens=200,
#     )
#     response_text = response.choices[0].message.content
#     # Convert text response to speech
#     for audio_chunk in tts_model.stream_tts_sync(response_text):
#         yield audio_chunk

# # Set up the FastRTC stream
# stream = Stream(
#     handler=ReplyOnPause(respond),
#     modality="audio",
#     mode="send-receive"
# )

# # Create a FastAPI app
# app = FastAPI()

# # Mount the FastRTC stream onto the FastAPI app
# stream.mount(app)

# # Run the FastAPI app with Uvicorn
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)