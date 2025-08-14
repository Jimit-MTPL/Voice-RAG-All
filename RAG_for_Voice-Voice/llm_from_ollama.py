import os
from flask import Flask, request, jsonify
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_community.llms.ollama import Ollama
from langchain.chains.retrieval import create_retrieval_chain
from dotenv import load_dotenv
from huggingface_hub import login
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
import time
from langchain.schema import AIMessage, HumanMessage
from collections import deque
from typing import List
from werkzeug.utils import secure_filename
import shutil
from transformers import pipeline
from langchain_huggingface import HuggingFacePipeline

# Initialize Flask app
app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = os.path.basename("pdfs")
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
def login_to_huggingface():
    login(token="")
    print("Logged in to Hugging Face")

login_to_huggingface()

# Model and Embedding setup
BGE_MODEL = "BAAI/bge-small-en-v1.5"
CHROMA_DB_PATH = "chromadb"
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')


embedding_model = HuggingFaceEmbeddings(model_name=BGE_MODEL, encode_kwargs={'normalize_embeddings': True})


# groq_model = ChatGroq(
#     model="llama-3.3-70b-versatile",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
#     api_key=GROQ_API_KEY
# )

ollama_model = Ollama(model="phi3:latest")

# Text splitter configuration
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=30,
    length_function=len,
    separators=["\n\n", "\n", ".", " ", ""]
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
#chat_history = deque(maxlen=6)
def reset_vector_store():
    """Remove the existing Chroma database with proper cleanup"""
    global vector_store
    try:
        if vector_store is not None:
            vector_store.delete_collection()
            vector_store = None
            #chat_history.clear()
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

# Function to initialize the vector store with PDF documents
def initialize_vector_store(documents):
    split_docs = split_documents(documents)
    vector_store = Chroma.from_documents(split_docs, embedding_model, persist_directory=os.path.basename(CHROMA_DB_PATH), collection_metadata={"hnsw:space": "cosine"})
    return vector_store

# Initialize memory for chat history
#memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Function to create the RAG system with memory
def create_rag_system(vector_store):
    system_prompt = (
        "You are a helpful and professional customer service representative handling phone calls for our application. "
        "Your primary role is to provide accurate information from our FAQs. Follow these strict guidelines:\n\n"
        "1. MOST IMPORTANT: When an exact match is found in the FAQs, provide that answer verbatim without any modifications\n"
        # "2. Don't mention phrases like 'according to FAQs' or 'I have found answer to your question in FAQs' in the response. Just find answer from knowledge and give response as it is.\n"
        "3. Do not add, remove, or modify any information from the FAQ answers\n"
        "4. Only for questions not directly covered in FAQs:\n"
        "   - First try to find if any closely related FAQ exists\n"
        "   - If no relevant information exists, say: 'I apologize, but I don't have specific information about that in my knowledge base.'\n"
        "5. Do not make up or infer information that's not explicitly stated in the FAQs\n"
        "6. Keep the phone conversation natural but prioritize accuracy over conversation flow\n"
        "7. If you need clarification to find the right FAQ, ask simple, direct questions\n"
        "8. End conversations naturally by asking 'Is there anything else I can help you with?' and if not, close with a simple 'Thank you for calling, have a great day!'\n\n"
        "Context from FAQs: {context}\n"
        #"Chat History: {chat_history}\n"
        "Current Question: {input}\n"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})
    question_answer_chain = create_stuff_documents_chain(ollama_model, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    return rag_chain

vector_store = None
rag_system = None

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
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        if file and allowed_file(file.filename):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                print("before resetting")
                print(vector_store)
                reset_vector_store()
                print("after resetting")
                documents = load_document(filepath)
                print(vector_store)
                vector_store = initialize_vector_store(documents)
                print(vector_store)
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

@app.route('/ask', methods=['POST'])
def ask_question():
    """Query the RAG system with a question and maintain chat history."""
    t_start = time.time()
    question = request.json.get("question")

    if not question:
        return jsonify({"error": "question is required"}), 400

    if not vector_store or not rag_system:
        return jsonify({"error": "No documents loaded. Please upload a PDF file first."}), 400

    #chat_history.append(HumanMessage(content=question))
    response = rag_system.invoke({"input": question})
    answer = response.get("answer", "No answer found")

    #chat_history.append(AIMessage(content=answer))
    # serialized_chat_history = [
    #     {"role": "user", "content": msg.content} if isinstance(msg, HumanMessage)
    #     else {"role": "assistant", "content": msg.content} 
    #     for msg in chat_history
    # ]

    t_end = time.time()
    t_taken = t_end - t_start
    
    return jsonify({
        "answer": answer, 
        "time": t_taken, 
        #"chat_history": serialized_chat_history
    }), 200

if __name__ == '__main__':
    print("🎙 Server is ready to take questions!")
    app.run(debug=True, host="0.0.0.0", port=8001)