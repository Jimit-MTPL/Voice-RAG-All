import os
from flask import Flask, request, jsonify, send_file
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader
#from langchain_community.embeddings import HuggingFaceEmbeddings
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
# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = os.path.basename("pdfs")
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Dictionary to store chat histories for different sessions
chat_histories: Dict[str, deque] = {}

def get_or_create_chat_history(sid: str) -> deque:
    """Get or create a new chat history for the given session ID"""
    if sid not in chat_histories:
        chat_histories[sid] = deque(maxlen=6)
    return chat_histories[sid]

# Model and Embedding setup
#BGE_MODEL = "BAAI/bge-small-en-v1.5"
CHROMA_DB_PATH = "chromadb"
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Load HuggingFace embeddings
embedding_model = HuggingFaceEmbeddings(model_name="models/bge-small-en-v1.5", encode_kwargs={'normalize_embeddings': True})

# Initialize Groq LLM
groq_model = ChatGroq(
    model="llama3-70b-8192",
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

def reset_vector_store():
    """
    Reset vector store and optionally clear chat history for a specific session
    Args:
        sid (str, optional): Session ID to clear history for. If None, clears all histories.
    """
    global vector_store
    try:
        if vector_store is not None:
            vector_store.delete_collection()
            vector_store = None
            chat_histories.clear()
        # add sid: str = None in argument
        # Clear chat history for specific session or all sessions
        # if sid:
        #     if sid in chat_histories:
        #         del chat_histories[sid]
        # else:
        #     chat_histories.clear()
            
    except Exception as e:
        print(f"Error in reset_vector_store: {str(e)}")
        raise e

def split_documents(documents):
    return text_splitter.split_documents(documents)

def load_document(filepath):
    """Load document based on file extension"""
    file_extension = filepath.split('.')[-1].lower()
    if file_extension == 'pdf':
        loader = PyPDFLoader(filepath)
    elif file_extension == 'txt':
        loader = TextLoader(filepath, encoding='utf-8')
    elif file_extension == 'csv':
        loader = CSVLoader(filepath)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")
    return loader.load()

def initialize_vector_store(documents):
    split_docs = split_documents(documents)
    vector_store = Chroma.from_documents(split_docs, embedding_model, persist_directory=os.path.basename(CHROMA_DB_PATH), collection_metadata={"hnsw:space": "cosine"})
    return vector_store

def create_rag_system(vector_store):
    system_prompt = (
        "You are a helpful and professional customer service representative handling phone calls for our application. "
        "Your primary role is to provide accurate information from our FAQs. Follow these strict guidelines:\n\n"
        "1. MOST IMPORTANT: When an exact match is found in the FAQs, provide that answer verbatim without any modifications\n"
        "2. Do not add, remove, or modify any information from the FAQ answers\n"
        # "3. Only for questions not directly covered in FAQs:\n"
        # "   - First try to find if any closely related FAQ exists\n"
        # "   - If no relevant information exists, say: 'I apologize, but I don't have specific information about that in my knowledge base.'\n"
        "3. If a question is outside of the knowledge base (not covered in FAQs), do not answer it. Instead, respond with:"
        "   - I am sorry, but I do not have details on that topic."
        "4. Do not make up or infer information that's not explicitly stated in the FAQs\n"
        "5. Keep the phone conversation natural but prioritize accuracy over conversation flow\n"
        "6. If you need clarification to find the right FAQ, ask simple, direct questions\n"
        "7. End conversations naturally by asking 'Is there anything else I can help you with?' and if not, close with a simple 'Thank you for calling, have a great day!'\n\n"
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

# Initialize global variables
vector_store = None
rag_system = None

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload a single PDF file and update the vector store.
    Removes existing file and recreates the vector store from scratch.
    """
    global vector_store, rag_system
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    # sid = request.form.get('sid')  # Optional: Get sid if you want to reset specific session
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        if file and allowed_file(file.filename):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Reset vector store and optionally clear specific session history
                # reset_vector_store(sid)
                reset_vector_store()
                documents = load_document(filepath)
                vector_store = initialize_vector_store(documents)
                rag_system = create_rag_system(vector_store)
                
                os.remove(filepath)
                
                return jsonify({
                    "message": "File processed and vector store updated successfully",
                    "processed_file": filename
                }), 200
            except Exception as pe:
                print(f"Processing error: {str(pe)}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                raise pe
                
        else:
            return jsonify({"error": "Invalid file type. Only PDF files are allowed"}), 400
        
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset_session():
    """Reset chat history for a specific session"""
    data = request.json
    sid = data.get('sid')
    print("sid in reset")
    print(sid)
    if not sid:
        return jsonify({"error": "sid is required"}), 400
        
    try:
        # reset_vector_store(sid)
        if sid in chat_histories:
            del chat_histories[sid]
            return jsonify({"message": f"Chat history cleared for session {sid}"}), 200
        else:
            print("session ID not found")
            #return jsonify({"error": "Session ID not found"}), 404
            return jsonify({"message": f"Chat history not found for session {sid}"}), 200
    except Exception as e:
        print("Exception")
        print(str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """Query the RAG system with a question and maintain chat history per session."""
    t_start = time.time()
    
    data = request.json
    question = data.get("question")
    sid = data.get("sid")
    print("sid in ask")
    print(sid)
    if not question or not sid:
        return jsonify({"error": "Both question and sid are required"}), 400

    if not vector_store or not rag_system:
        return jsonify({"error": "No documents loaded. Please upload a PDF file first."}), 400

    # Get or create chat history for this session
    chat_history = get_or_create_chat_history(sid)
    
    chat_history.append(HumanMessage(content=question))
    response = rag_system.invoke({"input": question, "chat_history": list(chat_history)})
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

save_audio_path = "output_files"
os.makedirs(save_audio_path, exist_ok=True)

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    file_path = os.path.join(save_audio_path, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    print("🎙 Server is ready to take questions!")
    app.run(debug=True, host="0.0.0.0", port=8005)


