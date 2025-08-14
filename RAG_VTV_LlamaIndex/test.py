import requests

# Define the URL of your Flask server
URL = "http://192.168.0.197:8002/chat"

# Define the payload (question to ask the RAG system)
payload = {"message": "what are the options available for pizza? "}

# Send the POST request
response = requests.post(URL, json=payload)

# Print the response
if response.status_code == 200:
    print("Response:", response.json())
else:
    print("Error:", response.status_code, response.text)
