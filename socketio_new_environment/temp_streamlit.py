import streamlit as st
import requests
import json

st.set_page_config(page_title="Chatbot UI", page_icon="💬")

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# Custom CSS to improve the appearance
st.markdown("""
<style>
.chat-message {
    padding: 0.7rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
    display: flex;
    flex-direction: row;
    align-items: center;
}
.chat-message.user {
    background-color: #e6f7ff;
    color: #000000;
}
.chat-message.assistant {
    background-color: #f0f2f6;
    color: #000000;
}
.chat-message .avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 0.5rem;
    font-size: 1.2rem;
}
.chat-message .message {
    flex-grow: 1;
    padding: 0.2rem 0;
    line-height: 1.4;
}
</style>
""", unsafe_allow_html=True)

st.title("Chatbot")
st.subheader("Ask me anything!")

# API endpoint configuration
api_url = "http://192.168.2.102:5000/api/code_assistance"  # Replace with your actual API endpoint

# Display chat history
for message in st.session_state.messages:
    with st.container():
        st.markdown(f"""
        <div class="chat-message {message['role']}">
            <div class="avatar">
                {'👤' if message['role'] == 'user' else '🤖'}
            </div>
            <div class="message">
                {message['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)

# Chat input
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area("Your message:", key="user_input", height=100)
    submit_button = st.form_submit_button("Send")

    if submit_button and user_input:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        try:
            # Send message to API
            payload = {"query": user_input}
            response = requests.post(api_url, json=payload)
            
            if response.status_code == 200:
                # Extract answer from API response
                answer = response.json().get("response", "Sorry, I couldn't process your request.")
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": answer})
            else:
                st.error(f"Error: API returned status code {response.status_code}")
                st.session_state.messages.append({"role": "assistant", "content": f"Sorry, there was an error processing your request. Status code: {response.status_code}"})
        
        except Exception as e:
            st.error(f"Error connecting to API: {str(e)}")
            st.session_state.messages.append({"role": "assistant", "content": "Sorry, I couldn't connect to the backend service."})
        
        # Rerun to update the UI with the new messages
        st.rerun()