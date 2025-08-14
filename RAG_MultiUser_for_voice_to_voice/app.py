import os
from flask import Flask, request, jsonify, session
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain.chains.retrieval import create_retrieval_chain
from dotenv import load_dotenv
from huggingface_hub import login
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import AIMessage, HumanMessage
from collections import deque
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime, timedelta
import time
import shutil

# def login_to_huggingface():
#     login(token="")
#     print("Logged in to Hugging Face")

# login_to_huggingface()
# Initialize Flask app
app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv('FLASK_SECRET_KEY')  # Required for session management

# Configuration
UPLOAD_FOLDER = os.path.basename("pdfs")
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# User session management
class UserSession:
    def __init__(self):
        self.vector_store = None
        self.rag_system = None
        self.chat_history = deque(maxlen=6)
        self.last_activity = datetime.now()

# Store user sessions
user_sessions = {}

# Session cleanup configuration
SESSION_TIMEOUT = timedelta(hours=1)

def cleanup_inactive_sessions():
    """Remove inactive user sessions"""
    current_time = datetime.now()
    inactive_users = [
        user_id for user_id, session in user_sessions.items()
        if current_time - session.last_activity > SESSION_TIMEOUT
    ]
    for user_id in inactive_users:
        del user_sessions[user_id]

def get_or_create_user_session():
    """Get existing user session or create a new one"""
    cleanup_inactive_sessions()
    
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    user_id = session['user_id']
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession()
    
    user_sessions[user_id].last_activity = datetime.now()
    return user_sessions[user_id]

# Rest of your existing configurations
BGE_MODEL = "BAAI/bge-small-en-v1.5"
CHROMA_DB_PATH = "chromadb"


# Model setup
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
embedding_model = HuggingFaceEmbeddings(model_name="models/bge-small-en-v1.5", encode_kwargs={'normalize_embeddings': True})
groq_model = ChatGroq(
    model="llama-3.3-70b-specdec",
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

def reset_vector_store(user_session):
    """Reset vector store for a specific user"""
    try:
        if user_session.vector_store is not None:
            print("==================vector store before deletion============================")
            print(user_session.vector_store)
            user_session.vector_store.delete_collection()
            #shutil.rmtree(os.path.join(os.path.basename(CHROMA_DB_PATH), session['user_id']))
            print("================vector store after deletion===============================")
            print(user_session.vector_store)
            user_session.vector_store = None
            user_session.chat_history.clear()
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

def initialize_vector_store(documents, user_id):
    """Initialize vector store for a specific user"""
    split_docs = split_documents(documents)
    persist_directory = os.path.join(os.path.basename(CHROMA_DB_PATH), user_id)
    os.makedirs(persist_directory, exist_ok=True)
    
    return Chroma.from_documents(
        split_docs, 
        embedding_model, 
        persist_directory=persist_directory,
        collection_metadata={"hnsw:space": "cosine"}
    )

def create_rag_system(vector_store):
    """Create RAG system with the same prompt template as before"""
    system_prompt = (
        "You are a helpful and professional customer service representative handling phone calls for our application. "
        "Your primary role is to provide accurate information from our FAQs. Follow these strict guidelines:\n\n"
        "1. MOST IMPORTANT: When an exact match is found in the FAQs, provide that answer verbatim without any modifications\n"
        "2. Do not add, remove, or modify any information from the FAQ answers\n"
        "3. Only for questions not directly covered in FAQs:\n"
        "   - First try to find if any closely related FAQ exists\n"
        "   - If no relevant information exists, say: 'I apologize, but I don't have specific information about that in my knowledge base.'\n"
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
    return create_retrieval_chain(retriever, question_answer_chain)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload a file for a specific user"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        if file and allowed_file(file.filename):
            user_session = get_or_create_user_session()
            
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                reset_vector_store(user_session)
                documents = load_document(filepath)
                user_session.vector_store = initialize_vector_store(documents, session['user_id'])
                vector_store = initialize_vector_store(documents, session['user_id'])
                vector_store
                print("==================vectore store new==========================")
                print(user_session.vector_store)
                user_session.rag_system = create_rag_system(user_session.vector_store)
                
                os.remove(filepath)
                
                return jsonify({
                    "message": "File processed and vector store updated successfully",
                    "processed_file": filename
                }), 200
            except Exception as pe:
                if os.path.exists(filepath):
                    os.remove(filepath)
                raise pe
                
        else:
            return jsonify({"error": "Invalid file type"}), 400
        
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """Query the RAG system for a specific user"""
    t_start = time.time()
    question = request.json.get("question")

    if not question:
        return jsonify({"error": "question is required"}), 400

    user_session = get_or_create_user_session()
    if not user_session.vector_store or not user_session.rag_system:
        return jsonify({"error": "No documents loaded. Please upload a file first."}), 400

    user_session.chat_history.append(HumanMessage(content=question))
    response = user_session.rag_system.invoke({
        "input": question, 
        "chat_history": list(user_session.chat_history)
    })
    answer = response.get("answer", "No answer found")

    user_session.chat_history.append(AIMessage(content=answer))
    serialized_chat_history = [
        {"role": "user", "content": msg.content} if isinstance(msg, HumanMessage)
        else {"role": "assistant", "content": msg.content} 
        for msg in user_session.chat_history
    ]

    t_end = time.time()
    t_taken = t_end - t_start
    
    return jsonify({
        "answer": answer, 
        "time": t_taken, 
        "chat_history": serialized_chat_history
    }), 200

if __name__ == '__main__':
    print("🎙 Multi-user RAG Server is ready!")
    app.run(debug=True, host="0.0.0.0", port=8005)