import requests

# Define API URL (Change if running on a different host/port)
API_URL = "http://192.168.0.197:8502/upload"

# Path to the PDF file you want to upload
PDF_FILE_PATH = "Insurance_FAQ.txt"

# Open the file in binary mode
with open(PDF_FILE_PATH, "rb") as file:
    files = {"file": (PDF_FILE_PATH, file)}
    
    # Make the POST request
    response = requests.post(API_URL, files=files)
    
# Print the response from the server
print("Response Status Code:", response.status_code)
print("Response JSON:", response.json())
# import requests

# def upload_file(file_path, session_id):
#     url = "http://192.168.0.197:8502/upload"
    
#     files = {
#         'file': open(file_path, 'rb')
#     }
#     data = {
#         'sid': session_id
#     }
    
#     try:
#         response = requests.post(url, files=files, data=data)
#         print(f"Status Code: {response.status_code}")
#         print(f"Response: {response.json()}")
#     finally:
#         files['file'].close()

# # Example usage
# file_path = "Ujamaa-restaurant-menu.pdf"  # Replace with your file path
# session_id = "user_4"    # Replace with your session ID

# upload_file(file_path, session_id)