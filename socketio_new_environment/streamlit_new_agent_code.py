import streamlit as st
import requests
import json

st.set_page_config(page_title="Chatbot UI", page_icon="💬")

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

if "loading" not in st.session_state:
    st.session_state.loading = False

# Custom CSS to improve the appearance
st.markdown("""
<style>
.chat-message {
    padding: 0.7rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
    display: flex;
    flex-direction: row;
    align-items: flex-start;
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
    flex-shrink: 0;
    margin-top: 0.1rem;
}
.chat-message .message {
    flex-grow: 1;
    padding: 0.2rem 0;
    line-height: 1.4;
    word-wrap: break-word;  /* Enable word wrapping */
    overflow-wrap: break-word;  /* Modern version of word-wrap */
    word-break: break-word;  /* Allow words to break if needed */
    max-width: calc(100% - 40px);  /* Ensure text doesn't exceed container width */
}
/* Make containers responsive */
.stContainer {
    max-width: 100%;
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
        st.session_state.loading = True
        st.rerun()
    if st.session_state.loading:
        try:
            last_user_message = next((msg["content"] for msg in reversed(st.session_state.messages) if msg["role"] == "user"), None)
            # Send message to API
            response = requests.post(
                api_url,
                json={"query": last_user_message}
            )
            
            if response.status_code == 200:
                # Extract answer from API response
                answer = response.json().get("response", "Sorry, I couldn't process your request.")
                print(answer)
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": answer})
            else:
                st.error(f"Error: API returned status code {response.status_code}")
                st.session_state.messages.append({"role": "assistant", "content": f"Sorry, there was an error processing your request. Status code: {response.status_code}"})
        
        except Exception as e:
            st.error(f"Error connecting to API: {str(e)}")
            st.session_state.messages.append({"role": "assistant", "content": "Sorry, I couldn't connect to the backend service."})
        st.session_state.loading = False
        # Rerun to update the UI with the new messages
        st.rerun()