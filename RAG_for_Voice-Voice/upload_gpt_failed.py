import os
import glob
import shutil
from flask import Flask, request, jsonify
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain.chains.retrieval import create_retrieval_chain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from huggingface_hub import login
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
#from langchain.memory import ConversationBufferMemory  
import time
from langchain.schema import AIMessage, HumanMessage
from collections import deque
from werkzeug.utils import secure_filename


# Initialize Flask app
app = Flask(__name__)
def login_to_huggingface():
    login(token="")
    print("Logged in to Hugging Face")

login_to_huggingface()
# Configurations
UPLOAD_FOLDER = "uploads"
CHROMA_DB_PATH = "chromadb"
BGE_MODEL = "BAAI/bge-small-en-v1.5"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure upload folder exists

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize embedding model
embedding_model = HuggingFaceEmbeddings(
    model_name=BGE_MODEL, encode_kwargs={"normalize_embeddings": True}
)

# Initialize Groq LLM
groq_model = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=GROQ_API_KEY,
)

# Text Splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=30,
    length_function=len,
    separators=["\n\n", "\n", ".", " ", ""],
)

# Delete existing Chroma DB and initialize a new one
def reset_vector_store():
    if os.path.exists(CHROMA_DB_PATH):
        try:
            # 🔹 Ensure Chroma is properly closed before deletion
            vector_store = Chroma(persist_directory=CHROMA_DB_PATH)
            vector_store.delete_collection()  # Delete all stored data
            #del vector_store  # Explicitly remove the object
            
            #time.sleep(2)  # 🔹 Small delay to ensure release of file locks
            
            #shutil.rmtree(CHROMA_DB_PATH)  # Now delete the directory
            print("✅ Deleted old Chroma vector store collection.")
        except Exception as e:
            print(f"❌ Error while deleting Chroma DB: {e}")
            return None  # Exit if deletion fails

    # 🔹 Create a fresh Chroma DB
    #os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    Chroma_new = Chroma(persist_directory=CHROMA_DB_PATH, collection_name="quickstart")
    print("✅ New Chroma vector store initialized.")

    return Chroma_new

# Function to process a new PDF file
def process_pdf(file_path):
    """Processes a single PDF file, extracts text, splits it, and stores in the vector database."""
    
    # Delete old vector database and create a new one
    vector_store = reset_vector_store()
    
    # Load the new PDF
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    
    # Split into chunks
    split_docs = text_splitter.split_documents(documents)
    
    # Store in the vector database
    vector_store = Chroma.from_documents(
        split_docs, embedding_model, persist_directory=CHROMA_DB_PATH
    )
    return vector_store
#memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
# RAG System Creation
def create_rag_system(vector_store):
    system_prompt = (
        "You are a friendly and efficient cafe assistant designed for telephonic conversations. You have access to the cafe's menu by knowledge provided in documents.\n"
        "When answering customer queries, keep responses brief and to the point, avoiding unnecessary details unless specifically asked. Maintain a natural and conversational tone.\n"
        "For order-taking, confirm each item added but do not mention prices or the total during the process. Only summarize the complete order and total price at the end before final confirmation.\n"
        "When listing menu items, do not describe ingredients unless the customer specifically asks.\n"
        "If a customer asks about promotions, ingredients, or recommendations, provide concise but helpful responses.\n"
        "If asked a question beyond your knowledge, politely let them know and suggest contacting the cafe directly.\n"
        "After confirming the final order, ask if the customer wants delivery or takeout. If delivery, ask for the delivery address. If takeout, inform them how long it will take (e.g., 30 to 45 minutes).\n"
        "After getting information about delivery or takeout politely ask for any other help the customer needs and if customer don't need anything else, initiate end of conversation by saying something like good bye have a nice day.\n"
        "Context: {context}\n"
        "Chat History: {chat_history}\n"
        "Current Question: {input}\n"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )

    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})
    question_answer_chain = create_stuff_documents_chain(groq_model, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    return rag_chain

# Initialize Vector Store
vector_store = None
rag_system = None

# Chat History
chat_history = deque(maxlen=8)

# Ask Question Endpoint
@app.route("/ask", methods=["POST"])
def ask_question():
    """Query the RAG system with a question and maintain chat history."""
    t_start = time.time()
    question = request.json.get("question")

    if not question:
        return jsonify({"error": "question is required"}), 400

    chat_history.append(HumanMessage(content=question))

    response = rag_system.invoke({"input": question, "chat_history": list(chat_history)})
    answer = response.get("answer", "No answer found")

    chat_history.append(AIMessage(content=answer))

    serialized_chat_history = [
        {"role": "user", "content": msg.content}
        if isinstance(msg, HumanMessage)
        else {"role": "assistant", "content": msg.content}
        for msg in chat_history
    ]

    t_end = time.time()
    
    return jsonify({"answer": answer, "time": t_end - t_start, "chat_history": serialized_chat_history}), 200

# Upload PDF Endpoint
@app.route("/upload", methods=["POST"])
def upload_pdf():
    """Uploads a new PDF file, processes it, and stores it in the vector database."""
    
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    # Save file
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)
    
    # Process PDF and update the vector database
    global vector_store, rag_system
    vector_store = process_pdf(file_path)
    rag_system = create_rag_system(vector_store)
    
    return jsonify({"message": "PDF uploaded and processed successfully"}), 200

if __name__ == "__main__":
    print("🎙 Server is ready to take questions!")
    app.run(debug=True, host="0.0.0.0", port=8001)
