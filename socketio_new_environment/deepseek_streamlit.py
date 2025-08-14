# import streamlit as st
# import requests
# import json
# import time

# st.set_page_config(page_title="Chatbot UI", page_icon="💬")

# # Initialize chat history in session state if it doesn't exist
# if "messages" not in st.session_state:
#     st.session_state.messages = []

# # Initialize loading state
# if "loading" not in st.session_state:
#     st.session_state.loading = False

# # Custom CSS to improve the appearance
# st.markdown("""
# <style>
# .chat-message {
#     padding: 0.7rem;
#     border-radius: 0.5rem;
#     margin-bottom: 1rem;
#     display: flex;
#     flex-direction: row;
#     align-items: flex-start;
# }
# .chat-message.user {
#     background-color: #e6f7ff;
#     color: #000000;
# }
# .chat-message.assistant {
#     background-color: #f0f2f6;
#     color: #000000;
# }
# .chat-message .avatar {
#     width: 32px;
#     height: 32px;
#     border-radius: 50%;
#     display: flex;
#     align-items: center;
#     justify-content: center;
#     margin-right: 0.5rem;
#     font-size: 1.2rem;
#     flex-shrink: 0;
#     margin-top: 0.1rem;
# }
# .chat-message .message {
#     flex-grow: 1;
#     padding: 0.2rem 0;
#     line-height: 1.4;
#     word-wrap: break-word;  /* Enable word wrapping */
#     overflow-wrap: break-word;  /* Modern version of word-wrap */
#     word-break: break-word;  /* Allow words to break if needed */
#     max-width: calc(100% - 40px);  /* Ensure text doesn't exceed container width */
# }
# /* Make containers responsive */
# .stContainer {
#     max-width: 100%;
# }
# /* Hide Streamlit branding */
# #MainMenu {visibility: hidden;}
# footer {visibility: hidden;}
# /* Ensure code blocks wrap properly */
# code {
#     white-space: pre-wrap !important;
#     word-break: break-word !important;
# }
# /* Handle pre tags for code blocks */
# pre {
#     white-space: pre-wrap !important;
#     word-break: break-word !important;
#     overflow-x: auto;
# }
# </style>
# """, unsafe_allow_html=True)

# st.title("Chatbot")
# st.subheader("Ask me anything!")

# # API endpoint configuration
# api_url = "http://192.168.2.102:5000/api/code_assistance"  # Replace with your actual API endpoint

# # Display chat history
# for message in st.session_state.messages:
#     with st.container():
#         # Use markdown with HTML for proper text wrapping
#         st.markdown(f"""
#         <div class="chat-message {message['role']}">
#             <div class="avatar">
#                 {'👤' if message['role'] == 'user' else '🤖'}
#             </div>
#             <div class="message">
#                 {message['content']}
#             </div>
#         </div>
#         """, unsafe_allow_html=True)

# # Display loading spinner if we're waiting for a response
# if st.session_state.loading:
#     with st.container():
#         with st.spinner("Thinking..."):
#             # This container will show a spinner while waiting for response
#             st.empty()

# # Chat input
# with st.form(key="chat_form", clear_on_submit=True):
#     user_input = st.text_area("Your message:", key="user_input", height=100)
#     submit_button = st.form_submit_button("Send")

#     if submit_button and user_input:
#         # Add user message to chat history
#         st.session_state.messages.append({"role": "user", "content": user_input})
#         # Set loading state to true
#         st.session_state.loading = True
#         # Rerun to display the user message and loading spinner
#         st.rerun()

# # Handle API request outside the form to allow for the loading spinner
# if st.session_state.loading:
#     try:
#         # Get the last user message
#         last_user_message = next((msg["content"] for msg in reversed(st.session_state.messages) 
#                                if msg["role"] == "user"), None)
        
#         if last_user_message:
#             # Send message to API
#             payload = {"query": last_user_message}
#             response = requests.post(api_url, json=payload)
            
#             if response.status_code == 200:
#                 # Extract answer from API response
#                 answer = response.json().get("response", "Sorry, I couldn't process your request.")
                
#                 # Add assistant response to chat history
#                 st.session_state.messages.append({"role": "assistant", "content": answer})
#             else:
#                 st.session_state.messages.append({"role": "assistant", "content": f"Sorry, there was an error processing your request. Status code: {response.status_code}"})
    
#     except Exception as e:
#         st.session_state.messages.append({"role": "assistant", "content": f"Sorry, I couldn't connect to the backend service. Error: {str(e)}"})
    
#     # Set loading state back to false
#     st.session_state.loading = False
#     # Rerun to update the UI with the new messages and remove the spinner
#     st.rerun()

# import streamlit as st
# import requests
# import re

# st.set_page_config(page_title="Chatbot UI", page_icon="💬")

# # Initialize chat history in session state if it doesn't exist
# if "messages" not in st.session_state:
#     st.session_state.messages = []

# # Initialize loading state
# if "loading" not in st.session_state:
#     st.session_state.loading = False

# # Function to convert markdown code blocks to HTML
# def process_code_blocks(text):
#     # Process code blocks with language specification
#     pattern = r'```(\w+)?\n([\s\S]*?)\n```'
    
#     def replacement(match):
#         language = match.group(1) or ""
#         code = match.group(2)
#         return f'<div class="code-block"><div class="code-header">{language}</div><pre><code>{code}</code></pre></div>'
    
#     processed_text = re.sub(pattern, replacement, text)
    
#     # Process inline code
#     inline_pattern = r'`([^`]+)`'
#     processed_text = re.sub(inline_pattern, r'<code class="inline-code">\1</code>', processed_text)
    
#     return processed_text

# # Custom CSS to improve the appearance
# st.markdown("""
# <style>
# .chat-message {
#     padding: 0.7rem;
#     border-radius: 0.5rem;
#     margin-bottom: 1rem;
#     display: flex;
#     flex-direction: row;
#     align-items: flex-start;
# }
# .chat-message.user {
#     background-color: #e6f7ff;
#     color: #000000;
# }
# .chat-message.assistant {
#     background-color: #f0f2f6;
#     color: #000000;
# }
# .chat-message .avatar {
#     width: 32px;
#     height: 32px;
#     border-radius: 50%;
#     display: flex;
#     align-items: center;
#     justify-content: center;
#     margin-right: 0.5rem;
#     font-size: 1.2rem;
#     flex-shrink: 0;
#     margin-top: 0.1rem;
# }
# .chat-message .message {
#     flex-grow: 1;
#     padding: 0.2rem 0;
#     line-height: 1.4;
#     word-wrap: break-word;
#     overflow-wrap: break-word;
#     word-break: break-word;
#     max-width: calc(100% - 40px);
# }
# /* Code block styling */
# .code-block {
#     background-color: #272822;
#     border-radius: 5px;
#     margin: 1rem 0;
#     overflow: hidden;
# }
# .code-header {
#     background-color: #333;
#     color: #f8f8f2;
#     padding: 0.3rem 0.7rem;
#     font-size: 0.8rem;
#     font-family: monospace;
# }
# pre {
#     margin: 0;
#     padding: 0.7rem;
#     white-space: pre-wrap !important;
#     word-break: break-word !important;
#     overflow-x: auto;
# }
# code {
#     font-family: 'Courier New', Courier, monospace;
#     color: #f8f8f2;
#     white-space: pre-wrap !important;
#     word-break: break-word !important;
# }
# .inline-code {
#     background-color: #f1f1f1;
#     color: #e83e8c;
#     padding: 0.2rem 0.4rem;
#     border-radius: 3px;
#     font-size: 0.9rem;
# }
# /* Make containers responsive */
# .stContainer {
#     max-width: 100%;
# }
# /* Hide Streamlit branding */
# #MainMenu {visibility: hidden;}
# footer {visibility: hidden;}
# </style>
# """, unsafe_allow_html=True)

# st.title("Chatbot")
# st.subheader("Ask me anything!")

# # API endpoint configuration
# api_url = "http://192.168.2.102:5000/api/code_assistance"  # Replace with your actual API endpoint

# # Display chat history
# for message in st.session_state.messages:
#     with st.container():
#         # Process content to handle code blocks
#         processed_content = process_code_blocks(message['content'])
        
#         # Use markdown with HTML for proper text wrapping
#         st.markdown(f"""
#         <div class="chat-message {message['role']}">
#             <div class="avatar">
#                 {'👤' if message['role'] == 'user' else '🤖'}
#             </div>
#             <div class="message">
#                 {processed_content}
#             </div>
#         </div>
#         """, unsafe_allow_html=True)

# # Display loading spinner if we're waiting for a response
# if st.session_state.loading:
#     with st.container():
#         with st.spinner("Thinking..."):
#             # This container will show a spinner while waiting for response
#             st.empty()

# # Chat input
# with st.form(key="chat_form", clear_on_submit=True):
#     user_input = st.text_area("Your message:", key="user_input", height=100)
#     submit_button = st.form_submit_button("Send")

#     if submit_button and user_input:
#         # Add user message to chat history
#         st.session_state.messages.append({"role": "user", "content": user_input})
#         # Set loading state to true
#         st.session_state.loading = True
#         # Rerun to display the user message and loading spinner
#         st.rerun()

# # Handle API request outside the form to allow for the loading spinner
# if st.session_state.loading:
#     try:
#         # Get the last user message
#         last_user_message = next((msg["content"] for msg in reversed(st.session_state.messages) 
#                                if msg["role"] == "user"), None)
        
#         if last_user_message:
#             # Send message to API
#             payload = {"query": last_user_message}
#             response = requests.post(api_url, json=payload)
            
#             if response.status_code == 200:
#                 # Extract answer from API response
#                 answer = response.json().get("response", "Sorry, I couldn't process your request.")
#                 print(answer)
#                 # Add assistant response to chat history
#                 st.session_state.messages.append({"role": "assistant", "content": answer})
#             else:
#                 st.session_state.messages.append({"role": "assistant", "content": f"Sorry, there was an error processing your request. Status code: {response.status_code}"})
    
#     except Exception as e:
#         st.session_state.messages.append({"role": "assistant", "content": f"Sorry, I couldn't connect to the backend service. Error: {str(e)}"})
    
#     # Set loading state back to false
#     st.session_state.loading = False
#     # Rerun to update the UI with the new messages and remove the spinner
#     st.rerun()

# import streamlit as st
# import requests
# import re
# import html

# st.set_page_config(page_title="Chatbot UI", page_icon="💬")

# # Initialize chat history in session state if it doesn't exist
# if "messages" not in st.session_state:
#     st.session_state.messages = []

# # Initialize loading state
# if "loading" not in st.session_state:
#     st.session_state.loading = False

# # Function to process code blocks
# def process_markdown(text):
#     # First, let's escape any HTML in the text
#     text = html.escape(text)
    
#     # Process code blocks with language specification
#     # This pattern matches ```language and captures the language and code content
#     code_pattern = r'```(\w+)?\n([\s\S]*?)\n```'
    
#     def code_replacer(match):
#         lang = match.group(1) or ""
#         code = match.group(2)
#         # Create a properly styled code block with syntax highlighting cues
#         return f'''
#         <div class="code-block">
#             <div class="code-header">{lang}</div>
#             <pre><code class="language-{lang}">{code}</code></pre>
#         </div>
#         '''
    
#     # Replace code blocks
#     processed = re.sub(code_pattern, code_replacer, text)
    
#     # Process inline code
#     inline_pattern = r'`([^`]+)`'
#     processed = re.sub(inline_pattern, r'<code class="inline-code">\1</code>', processed)
    
#     # Process line breaks
#     processed = processed.replace('\n', '<br>')
    
#     return processed

# # Custom CSS for improved appearance
# st.markdown("""
# <style>
# .chat-message {
#     padding: 1rem;
#     border-radius: 0.5rem;
#     margin-bottom: 1rem;
#     display: flex;
#     flex-direction: row;
#     align-items: flex-start;
# }
# .chat-message.user {
#     background-color: #e6f7ff;
#     color: #000000;
# }
# .chat-message.assistant {
#     background-color: #f0f2f6;
#     color: #000000;
# }
# .chat-message .avatar {
#     width: 32px;
#     height: 32px;
#     border-radius: 50%;
#     display: flex;
#     align-items: center;
#     justify-content: center;
#     margin-right: 1rem;
#     font-size: 1.2rem;
#     flex-shrink: 0;
#     margin-top: 0.1rem;
# }
# .chat-message .message {
#     flex-grow: 1;
#     line-height: 1.5;
#     flex-grow: 1;
#     padding: 0.2rem 0;
#     line-height: 1.4;
#     word-wrap: break-word;
#     overflow-wrap: break-word;
#     word-break: break-word;
#     max-width: calc(100% - 40px);
# }
# /* Code block styling */
# .code-block {
#     margin: 1rem 0;
#     background-color: #272822;
#     border-radius: 5px;
#     overflow: hidden;
#     font-family: 'Courier New', monospace;
# }
# .code-header {
#     background-color: #333;
#     color: #f8f8f2;
#     padding: 0.3rem 0.7rem;
#     font-size: 0.9rem;
#     font-family: monospace;
# }
# .code-block pre {
#     margin: 0;
#     padding: 1rem;
#     overflow-x: auto;
# }
# .code-block code {
#     font-family: 'Courier New', monospace;
#     color: #f8f8f2;
#     white-space: pre;
# }
# .language-cpp .keyword { color: #F92672; }
# .language-cpp .string { color: #E6DB74; }
# .language-cpp .number { color: #AE81FF; }
# .language-cpp .comment { color: #75715E; }
# .language-cpp .function { color: #A6E22E; }
# .inline-code {
#     background-color: #f1f1f1;
#     color: #e83e8c;
#     padding: 0.2rem 0.4rem;
#     border-radius: 3px;
#     font-size: 0.9rem;
#     font-family: monospace;
# }
# /* Make containers responsive */
# .stContainer { max-width: 100%; }
# /* Hide Streamlit branding */
# #MainMenu {visibility: hidden;}
# footer {visibility: hidden;}
# </style>
# """, unsafe_allow_html=True)

# st.title("Chatbot")
# st.subheader("Ask me anything!")

# # API endpoint configuration
# api_url = "http://192.168.2.102:5000/api/code_assistance"  # Replace with your actual API endpoint

# # Display chat history
# for message in st.session_state.messages:
#     with st.container():
#         # Process content to properly handle markdown and code blocks
#         processed_content = process_markdown(message['content'])
        
#         # Use HTML for proper formatting
#         st.markdown(f"""
#         <div class="chat-message {message['role']}">
#             <div class="avatar">
#                 {'👤' if message['role'] == 'user' else '🤖'}
#             </div>
#             <div class="message">
#                 {processed_content}
#             </div>
#         </div>
#         """, unsafe_allow_html=True)

# # Display loading spinner if we're waiting for a response
# if st.session_state.loading:
#     with st.container():
#         with st.spinner("Thinking..."):
#             st.empty()

# # Chat input
# with st.form(key="chat_form", clear_on_submit=True):
#     user_input = st.text_area("Your message:", key="user_input", height=100)
#     submit_button = st.form_submit_button("Send")

#     if submit_button and user_input:
#         # Add user message to chat history
#         st.session_state.messages.append({"role": "user", "content": user_input})
#         # Set loading state to true
#         st.session_state.loading = True
#         # Rerun to display the user message and loading spinner
#         st.rerun()

# # Handle API request outside the form to allow for the loading spinner
# if st.session_state.loading:
#     try:
#         # Get the last user message
#         last_user_message = next((msg["content"] for msg in reversed(st.session_state.messages) 
#                                if msg["role"] == "user"), None)
        
#         if last_user_message:
#             # Send message to API
#             payload = {"query": last_user_message}
#             response = requests.post(api_url, json=payload)
            
#             if response.status_code == 200:
#                 # Extract answer from API response
#                 answer = response.json().get("response", "Sorry, I couldn't process your request.")
                
#                 # Add assistant response to chat history
#                 st.session_state.messages.append({"role": "assistant", "content": answer})
#             else:
#                 st.session_state.messages.append({"role": "assistant", "content": f"Sorry, there was an error processing your request. Status code: {response.status_code}"})
    
#     except Exception as e:
#         st.session_state.messages.append({"role": "assistant", "content": f"Sorry, I couldn't connect to the backend service. Error: {str(e)}"})
    
#     # Set loading state back to false
#     st.session_state.loading = False
#     # Rerun to update the UI with the new messages and remove the spinner
#     st.rerun()