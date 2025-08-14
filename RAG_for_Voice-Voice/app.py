import os
from flask import Flask, request, jsonify
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
#from langchain.memory import ConversationBufferMemory
import time
from langchain.schema import AIMessage, HumanMessage
from collections import deque
from typing import List
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
def login_to_huggingface():
    login(token="")
    print("Logged in to Hugging Face")

login_to_huggingface()

# Model and Embedding setup
BGE_MODEL = "BAAI/bge-small-en-v1.5"
CHROMA_DB_PATH = "chromadb"
load_dotenv()
# if os.path.exists(CHROMA_DB_PATH):
#     shutil.rmtree(CHROMA_DB_PATH)
# Access the API key from the environment
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Load HuggingFace embeddings
embedding_model = HuggingFaceEmbeddings(model_name=BGE_MODEL, encode_kwargs={'normalize_embeddings': True})

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
chat_history = deque(maxlen=6)
def reset_vector_store():
    """Remove the existing Chroma database with proper cleanup"""
    global vector_store
    try:
        # First, close the existing vector store connection if it exists
        if vector_store is not None:
            vector_store.delete_collection()
            #print(vector_store)
            vector_store = None
            chat_history.clear()
        
        # Now try to remove the directory
      # Give OS time to release file handles
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
        # "You are a friendly and efficient cafe assistant designed for telephonic conversations. You have access to the cafe's menu by knowledge provided in documents.\n"
        # "When answering customer queries, keep responses brief and to the point, avoiding unnecessary details unless specifically asked. Maintain a natural and conversational tone.\n"
        # "For order-taking, confirm each item added but do not mention prices or the total during the process. Only summarize the complete order and total price at the end before final confirmation.\n"
        # "When listing menu items, do not describe ingredients unless the customer specifically asks.\n"
        # "If a customer asks about promotions, ingredients, or recommendations, provide concise but helpful responses.\n"
        # "If asked a question beyond your knowledge, politely let them know and suggest contacting the cafe directly.\n"
        # "After confirming the final order, ask if the customer wants delivery or takeout. If delivery, ask for the delivery address. If takeout, inform them how long it will take (e.g., 30 to 45 minutes).\n"
        # "After getting information about delivery or takeout politely ask for any other help the customer needs and if customer don't need anything else, initiate end of conversation by saying something like good bye have a nice day.\n"
        # "Context: {context}\n"
        # "Chat History: {chat_history}\n"
        # "Current Question: {input}\n"
        # "You are a helpful and professional customer service representative handling phone calls for our application. "
        # "Your responses should be based on the FAQs which are provided to you as knowledge in documents. Follow these guidelines:\n\n"
        # "1. Keep responses concise, clear, and conversational - aim for a natural phone conversation tone\n"
        # "2. Use the exact information from the FAQs when available, but present it in a conversational way\n"
        # "3. If a question isn't directly covered in the FAQs:\n"
        # "   - Try to provide relevant information from the closest matching FAQ\n"
        # "   - If nothing relevant exists, politely explain that you'll need to transfer them to a human agent\n"
        # "4. Always maintain a helpful and patient tone, even with frustrated customers\n"
        # "5. If you need to clarify something, ask simple, direct questions\n"
        # "6. End conversations naturally by confirming if the customer needs anything else\n\n"
        # "Context from FAQs: {context}\n"
        # "Chat History: {chat_history}\n"
        # "Current Question: {input}\n"
        # "You are a helpful and professional customer service representative handling phone calls for our application. "
        # "Your primary role is to provide accurate information from our FAQs. Follow these strict guidelines:\n\n"
        # "1. MOST IMPORTANT: When an exact match is found in the FAQs, provide that answer verbatim without any modifications\n"
        # "2. Do not add, remove, or modify any information from the FAQ answers\n"
        # "3. Only for questions not directly covered in FAQs:\n"
        # "   - First try to find if any closely related FAQ exists\n"
        # "   - If no relevant information exists, say: 'I apologize, but I don't have specific information about that in my knowledge base. Let me transfer you to a human agent who can better assist you.'\n"
        # "4. Do not make up or infer information that's not explicitly stated in the FAQs\n"
        # "5. Keep the phone conversation natural but prioritize accuracy over conversation flow\n"
        # "6. If you need clarification to find the right FAQ, ask simple, direct questions\n"
        # "7. End conversations by asking if there are any other questions about topics covered in our FAQs\n\n"
        # "Context from FAQs: {context}\n"
        # "Chat History: {chat_history}\n"
        # "Current Question: {input}\n"
        "You are a helpful and professional customer service representative handling phone calls for our application. "
        "Your primary role is to provide accurate information from our FAQs. Follow these strict guidelines:\n\n"
        "1. MOST IMPORTANT: When an exact match is found in the FAQs, provide that answer verbatim without any modifications\n"
        "2. Do not add, remove, or modify any information from the FAQ answers\n"
        "3. Only for questions not directly covered in FAQs:\n"
        "   - First try to find if any closely related FAQ exists\n"
        "   - If no relevant information exists, say: 'I apologize, but I don't have specific information about that in my knowledge base.'\n"
        "4. If a question is outside of the knowledge base (not covered in FAQs), do not answer it. Instead, respond with:"
        "   - I’m sorry, but I don’t have details on that topic."
        "5. Do not make up or infer information that's not explicitly stated in the FAQs\n"
        "6. Keep the phone conversation natural but prioritize accuracy over conversation flow\n"
        "7. If you need clarification to find the right FAQ, ask simple, direct questions\n"
        "8. End conversations naturally by asking 'Is there anything else I can help you with?' and if not, close with a simple 'Thank you for calling, have a great day!'\n\n"
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
    
    # Check if any file was sent
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    # Check if file was selected
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        if file and allowed_file(file.filename):
            # Create necessary directories if they don't exist
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # Save new file first
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                print("before resetting")
                print(vector_store)
                reset_vector_store()
                print("after resetting")
                
                # Load new document
                # loader = PyPDFLoader(filepath)
                # documents = loader.load()
                documents = load_document(filepath)
                print(vector_store)
                # Initialize vector store and RAG system
                vector_store = initialize_vector_store(documents)
                print(vector_store)
                rag_system = create_rag_system(vector_store)
                
                # Remove the file after processing
                os.remove(filepath)
                
                return jsonify({
                    "message": "File processed and vector store updated successfully",
                    "processed_file": filename
                }), 200
            except Exception as pe:
                print(f"Processing error: {str(pe)}")
                # Clean up the uploaded file if processing fails
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
        "chat_history": serialized_chat_history
    }), 200

if __name__ == '__main__':
    print("🎙 Server is ready to take questions!")
    app.run(debug=True, host="0.0.0.0", port=8502)