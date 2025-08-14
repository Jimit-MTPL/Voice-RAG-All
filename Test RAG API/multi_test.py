import requests


# API endpoint
url = "http://localhost:8005/ask"

# First request
question1 = {"question": "How To Create A New Credit Note?"}
response1 = requests.post(url, json=question1, cookies={"session":"eyJ1c2VyX2lkIjoiYmM3NmFhNGEtMjI5ZS00Mzg0LWE4MjctY2U0ZmZkOWNmZTQyIn0.Z6s0xw.WQGMz45Fd_lldGf1q16aC90eJnY"})



print("First Response:", response1.json())

# Second request - use the same session cookie
# question2 = {"question": "What is your second question?"}
# response2 = requests.post(url, json=question2, cookies=session_cookie)

# print("Second Response:", response2.json())

# cookies={"session": "eyJ1c2VyX2lkIjoiOWQ2NjIzMTItYTBlNi00YTRhLThmYmYtMzMwZjM2MTBlZjZmIn0.Z6sVKw.Sz55uunMgjNsVGm67_5LWKrYtAw"}