import os
from flask import Flask, request, jsonify
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader, PyMuPDFLoader
from langchain_community.document_loaders.text import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain.chains.retrieval import create_retrieval_chain
from dotenv import load_dotenv
from huggingface_hub import login
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
import time
from langchain.schema import AIMessage, HumanMessage
from collections import deque
from typing import List, Dict
from werkzeug.utils import secure_filename
import shutil
from flask_cors import CORS
from marker.convert import convert_single_pdf
from marker.logger import configure_logging
from marker.models import load_all_models
from marker.output import save_markdown

# Initialize Flask app
app = Flask(__name__)
CORS(app)

class SessionState:
    def __init__(self):
        self.file_name = None
        self.md_file_path = None

session_state=SessionState()

# Configuration
UPLOAD_FOLDER = os.path.basename("pdfs")
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Dictionary to store chat histories and vector stores for different sessions
chat_histories: Dict[str, deque] = {}
vector_stores: Dict[str, Chroma] = {}
rag_systems: Dict[str, any] = {}

def get_or_create_chat_history(sid: str) -> deque:
    """Get or create a new chat history for the given session ID"""
    if sid not in chat_histories:
        chat_histories[sid] = deque(maxlen=8)
    return chat_histories[sid]

# Model and Embedding setup
BGE_MODEL = "BAAI/bge-small-en-v1.5"
CHROMA_DB_PATH = "chromadb"
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Load HuggingFace embeddings
embedding_model = HuggingFaceEmbeddings(model_name=BGE_MODEL, encode_kwargs={'normalize_embeddings': True})

# Initialize Groq LLM
groq_model = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=GROQ_API_KEY
)

# Text splitter configuration
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=30,
    length_function=len,
    separators=["\n\n", "\n", ".", " ", ""]
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def reset_vector_store(sid: str):
    """Reset vector store for a specific session"""
    try:
        if sid in vector_stores:
            vector_stores[sid].delete_collection()
            del vector_stores[sid]
        if sid in rag_systems:
            del rag_systems[sid]
        if sid in chat_histories:
            del chat_histories[sid]
    except Exception as e:
        print(f"Error in reset_vector_store for session {sid}: {str(e)}")
        raise e

def split_documents(documents):
    return text_splitter.split_documents(documents)

def load_document(filepath):
    """Load document based on file extension"""
    file_extension = filepath.split('.')[-1].lower()
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    if file_extension == 'pdf':
        model_lst = load_all_models()
        full_text, images, out_meta = convert_single_pdf(filepath, model_lst)
        subfolder_path = save_markdown('marker-output', base_name, full_text, images, out_meta)
        md_file_path = os.path.join(subfolder_path, f"{base_name}.md")
        loader = TextLoader(md_file_path)
        if not subfolder_path == session_state.md_file_path:
            print("inside md if")
            if session_state.md_file_path:
                print("inside md if if")
                shutil.rmtree(session_state.md_file_path)
            session_state.md_file_path = subfolder_path
            print(session_state.md_file_path)
        print(session_state.md_file_path)
        #os.remove(md_file_path)
        # loader = PyMuPDFLoader(filepath)
        # shutil.rmtree(subfolder_path)
    elif file_extension == 'txt':
        loader = TextLoader(filepath, encoding='utf-8')
    elif file_extension == 'csv':
        loader = CSVLoader(filepath)
    # elif file_extension == 'md':
    #     loader = TextLoader(filepath)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")
    return loader.load()

def initialize_vector_store(documents, sid: str):
    split_docs = split_documents(documents)
    persist_directory = os.path.join(os.path.basename(CHROMA_DB_PATH), sid)
    os.makedirs(persist_directory, exist_ok=True)
    vector_store = Chroma.from_documents(
        split_docs,
        embedding_model,
        persist_directory=persist_directory,
        collection_metadata={"hnsw:space": "cosine"}
    )
    return vector_store

def create_rag_system(vector_store):
    system_prompt = (
        "You are a helpful and professional assistant providing accurate information based on a given knowledge base."
        "Follow these strict guidelines to ensure reliability and clarity:\n\n"
        "1. Keep answers concise and to the point for smooth voice interactions.\n"
        "2. Do not add, remove, or modify any information from the knowledge base.\n"
        "3. If a question is outside of the knowledge base (not covered), do not answer it. Instead, respond with: I am sorry, but I don't have details on that topic.\n"
        "4. Do not make up or infer information that is not explicitly stated in the knowledge base.\n"
        "5. Keep the conversation natural but prioritize accuracy over flow.\n"
        "6. If you need clarification to find the right answer, ask simple, direct questions.\n"
        "7. End conversations naturally by asking, Is there anything else I can help with?\n\n"
        "Context from FAQs: {context}\n"
        "Chat History: {chat_history}\n"
        "Current Question: {input}\n"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})
    question_answer_chain = create_stuff_documents_chain(groq_model, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    return rag_chain

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload a single file and update the vector store for a specific session.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    sid = request.form.get('sid')
    
    if not sid:
        return jsonify({"error": "Session ID (sid) is required"}), 400
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        if file and allowed_file(file.filename):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                reset_vector_store(sid)
                # sid_path = os.path.join(os.path.basename(CHROMA_DB_PATH), sid)
                # sqlite_file = os.path.join(sid_path, "chroma.sqlite3")
                # if os.path.exists(sid_path):
                #     print("before deleting sqlite")
                #     os.remove(sqlite_file)  # Delete the chroma.sqlite3 file
                #     print("after deleting sqlite")
                #     print(f"Deleted: {sqlite_file}")

                #     # Now check and delete the folder
                #     for item in os.listdir(sid_path):
                #         item_path = os.path.join(sid_path, item)
                #         if os.path.isdir(item_path):  # Check if it's a folder
                #             shutil.rmtree(item_path)  # Delete the folder
                #             print(f"Deleted folder: {item_path}")
    #             def delete_file():
    #     # Wait a bit longer to ensure download is complete
    #                 for i in range(5):
    #                     time.sleep(1)
    #                     try:
    #                         if os.path.exists(sid_path):
    #                             os.remove(sqlite_file)
    #                             for item in os.listdir(sid_path):
    #                                 item_path = os.path.join(sid_path, item)
    #                                 if os.path.isdir(item_path):  # Check if it's a folder
    #                                     shutil.rmtree(item_path)  # Delete the folder
    #                                     print(f"Deleted folder: {item_path}")
    #                             return True
    #                     except Exception as e:
    #                             print(f"Error deleting file {filename}: {str(e)}")
    #                 return False

    # # Start deletion in background thread
    #             thread = threading.Thread(target=delete_file)
    #             thread.start()
    #             thread.join()
                documents = load_document(filepath)
                vector_stores[sid] = initialize_vector_store(documents, sid)
                rag_systems[sid] = create_rag_system(vector_stores[sid])
                # time.sleep(5)
                # if os.path.exists(sid_path):
                #     # Get all folders with their creation times
                    
                #     folders = []
                #     for item in os.listdir(sid_path):
                #         item_path = os.path.join(sid_path, item)
                #         if os.path.isdir(item_path):  # Check if it's a folder
                #             creation_time = os.path.getctime(item_path)
                #             folders.append((item_path, creation_time))
                    
                #     if folders:
                #         # Sort folders by creation time (newest first)
                #         folders.sort(key=lambda x: x[1], reverse=True)
                        
                #         # Skip the first (newest) folder and delete the rest
                #         for folder_path, _ in folders[1:]:
                #             retries = 3
                #             for attempt in range(retries):
                #                 try:
                #                     # shutil.rmtree(folder_path)
                #                     for item in os.listdir(folder_path):
                #                         item_path = os.path.join(folder_path, item)
                #                         if os.path.isfile(item_path):  # Check if it's a folder
                #                             os.remove(item_path)
                #                     print(f"Deleted old folder: {folder_path}")
                #                     break  # Successfully deleted, exit retry loop
                #                 except Exception as e:
                #                     print(f"Attempt {attempt + 1}: Error deleting {item_path}: {str(e)}")
                #                     if attempt < retries - 1:  # Don't sleep on last attempt
                #                         time.sleep(1)  # Wait a second before retrying
                # print("before pdf remove")
                # os.remove(filepath)
                # print("after pdf remove")
                if not filepath == session_state.file_name:
                    print("inside pdfs if")
                    if session_state.file_name:
                        print("inside pdfs if if")
                        print(session_state.file_name)
                        os.remove(session_state.file_name)
                    session_state.file_name = filepath
                    print(session_state.file_name)
                # session_state.file_name = filepath
                print(session_state.file_name)
                return jsonify({
                    "message": "File processed and vector store updated successfully",
                    "processed_file": filename,
                    "sid": sid
                }), 200
            except Exception as pe:
                print(f"Processing error: {str(pe)}")
                # if os.path.exists(filepath):
                #     os.remove(filepath)
                raise pe
                
        else:
            return jsonify({"error": "Invalid file type. Only PDF, TXT, and CSV files are allowed"}), 400
        
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset_session():
    """Reset chat history and vector store for a specific session"""
    data = request.json
    sid = data.get('sid')
    if not sid:
        return jsonify({"error": "sid is required"}), 400
        
    try:
        reset_vector_store(sid)
        return jsonify({"message": f"Session {sid} reset successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """Query the RAG system with a question and maintain chat history per session."""
    t_start = time.time()
    
    data = request.json
    question = data.get("question")
    sid = data.get("sid")
    
    if not question or not sid:
        return jsonify({"error": "Both question and sid are required"}), 400

    if sid not in vector_stores or sid not in rag_systems:
        return jsonify({"error": "No documents loaded for this session. Please upload a file first."}), 400

    # Get or create chat history for this session
    chat_history = get_or_create_chat_history(sid)
    
    chat_history.append(HumanMessage(content=question))
    response = rag_systems[sid].invoke({"input": question, "chat_history": list(chat_history)})
    answer = response.get("answer", "No answer found")

    chat_history.append(AIMessage(content=answer))
    
    serialized_chat_history = [
        {"role": "user", "content": msg.content} if isinstance(msg, HumanMessage)
        else {"role": "assistant", "content": msg.content} 
        for msg in chat_history
    ]

    t_end = time.time()
    t_taken = t_end - t_start
    
    return jsonify({
        "answer": answer, 
        "time": t_taken, 
        "chat_history": serialized_chat_history,
        "sid": sid
    }), 200

import os
from flask import Flask, send_file, jsonify, after_this_request
import threading

save_audio_path = "output_files"
os.makedirs(save_audio_path, exist_ok=True)

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    file_path = os.path.join(save_audio_path, filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    def delete_file():
        # Wait a bit longer to ensure download is complete
        time.sleep(2)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted file: {filename}")
        except Exception as e:
            print(f"Error deleting file {filename}: {str(e)}")

    # Start deletion in background thread
    threading.Thread(target=delete_file).start()

    return send_file(
        file_path, 
        as_attachment=True
    )

# @app.route('/download/<filename>', methods=['GET'])
# def download_file(filename):
#     file_path = os.path.join(save_audio_path, filename)
#     if os.path.exists(file_path):
#         try:
#             @after_this_request
#             def remove_file(response):
#                 try:
#                     if os.path.exists(file_path):
#                         os.remove(file_path)
#                         print(f"File {filename} was deleted after download")
#                 except Exception as e:
#                     print(f"Error deleting file {filename}: {str(e)}")
#                 return response

#             return send_file(file_path, as_attachment=True)
#         except Exception as e:
#             if os.path.exists(file_path):
#                 os.remove(file_path)
#             return jsonify({"error": str(e)}), 500
#     else:
#         return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    print("🎙 Server is ready to take questions!")
    app.run(debug=True, host="0.0.0.0", port=8502)