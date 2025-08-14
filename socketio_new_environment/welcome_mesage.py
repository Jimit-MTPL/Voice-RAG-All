text="Welcome to ChatBot-AI. your voice-powered assistant for seamless document conversations."

import requests
from dotenv import load_dotenv
import os
load_dotenv()
TTS_API_URL = os.getenv("TTS_API_URL")



payload = {"text": text}
response = requests.post(TTS_API_URL, json=payload)
os.makedirs("Welcome_mesage", exist_ok=True)
if response.status_code == 200:
    result = response.json()
    download_url = result.get('download_url', '')
    if download_url:
        file_name = os.path.basename(download_url)
        file_path = os.path.join("Welcome_mesage", file_name)
        audio_response = requests.get(download_url)
        if audio_response.status_code == 200:
            with open(file_path, "wb") as file:
                file.write(audio_response.content)
    else:
        print("Download URL not found in response")
else:
    print(f"API Error: Status code {response.status_code}")
    