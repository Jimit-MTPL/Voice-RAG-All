import base64
import requests
from openai import OpenAI

client = OpenAI()

# Fetch the audio file and convert it to a base64 encoded string
# url = "https://cdn.openai.com/API/docs/audio/alloy.wav"
# response = requests.get(url)
# response.raise_for_status()
# wav_data = response.content
# encoded_string = base64.b64encode(wav_data).decode('utf-8')

local_wav_path = "input_files\\audio_20250317_145424_543614.wav"  # Replace with your actual file path

# Read and encode the local audio file
with open(local_wav_path, "rb") as audio_file:
    wav_data = audio_file.read()
    encoded_string = base64.b64encode(wav_data).decode("utf-8")

completion = client.chat.completions.create(
    model="gpt-4o-audio-preview",
    modalities=["text", "audio"],
    audio={"voice": "alloy", "format": "wav"},
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": encoded_string,
                        "format": "wav"
                    }
                }
            ]
        },
    ]
)

print(completion.choices[0].message)
print("\n-----------------------\n")
print(completion.choices[0])

wav_bytes = base64.b64decode(completion.choices[0].message.audio.data)
with open("dog.wav", "wb") as f:
    f.write(wav_bytes)