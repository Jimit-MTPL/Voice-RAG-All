# import requests
# import time

# def test_file_uploads():
#     # API endpoint
#     upload_url = "http://localhost:8005/upload"
    
#     # First file upload
#     print("\n=== First File Upload ===")
#     with open('path/to/your/first/file.pdf', 'rb') as file1:
#         files = {'file': ('file1.pdf', file1, 'application/pdf')}
#         response1 = requests.post(upload_url, files=files)
        
#     print("First Upload Response:", response1.json())
#     print("First Upload Status Code:", response1.status_code)
    
#     # Save the session cookie from first response
#     session_cookie = response1.cookies
    
#     # Wait a bit before second upload (optional)
#     time.sleep(2)
    
#     # Second file upload - using same session
#     print("\n=== Second File Upload ===")
#     with open('path/to/your/second/file.pdf', 'rb') as file2:
#         files = {'file': ('file2.pdf', file2, 'application/pdf')}
#         response2 = requests.post(upload_url, files=files, cookies=session_cookie)
        
#     print("Second Upload Response:", response2.json())
#     print("Second Upload Status Code:", response2.status_code)
    
#     # Test if the chat history is cleared by making a test question
#     ask_url = "http://localhost:8005/ask"
#     test_question = {"question": "test question after second upload"}
#     ask_response = requests.post(ask_url, json=test_question, cookies=session_cookie)
#     print("\n=== Test Question After Second Upload ===")
#     print("Ask Response:", ask_response.json())

# if __name__ == "__main__":
#     test_file_uploads()

import requests

# Define API URL (Change if running on a different host/port)
API_URL = "http://127.0.0.1:8005/upload"

# Path to the PDF file you want to upload
PDF_FILE_PATH = "credit_note.txt"

# Open the file in binary mode
with open(PDF_FILE_PATH, "rb") as file:
    files = {"file": (PDF_FILE_PATH, file, "application/pdf")}
    
    # Make the POST request
    response = requests.post(API_URL, files=files, cookies={"session":"eyJ1c2VyX2lkIjoiMWI3N2I0MTYtN2IwZC00YWRkLTlkMTEtNDc1ZDIyZDU2NjQwIn0.Z6s71Q.ad3FWlmWLoGhtYHsOY5Ksny4ylY"})
    
# Print the response from the server
print("Response Status Code:", response.status_code)
print("Response JSON:", response.json())
session_cookie = response.cookies
print("Session Cookie:", session_cookie)
