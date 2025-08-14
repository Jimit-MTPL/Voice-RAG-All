#from langchain.chains.retrieval import create_retrieval_chain

import requests

# Define the URL of your Flask server
URL = "http://192.168.0.197:8502/ask"

# Define the payload (question to ask the RAG system)
payload = {"question": "i don't have insurance ", "sid":"user_1"}

# Send the POST request
response = requests.post(URL, json=payload)

# Print the response
if response.status_code == 200:
    print("Response:", response.json())
else:
    print("Error:", response.status_code, response.text)
