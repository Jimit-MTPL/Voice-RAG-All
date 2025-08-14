from typing import List, Dict
from collections import deque
from functools import lru_cache
import time
import glob
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain.schema.messages import HumanMessage, AIMessage
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from huggingface_hub import login

# Initialize FastAPI
app = FastAPI()

# Model and Embedding setup
BGE_MODEL = "BAAI/bge-small-en-v1.5"
CHROMA_DB_PATH = "chromadb"
PDF_FOLDER_PATH = "pdfs"

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Initialize embedding model
embedding_model = HuggingFaceEmbeddings(
    model_name=BGE_MODEL,
    encode_kwargs={'normalize_embeddings': True}
)

# Initialize Groq LLM
groq_model = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=GROQ_API_KEY
)

# Initialize text splitter with optimized settings
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=20,
    length_function=len,
    separators=["\n\n", "\n", ".", " ", ""]
)

# Initialize chat history with fixed size
chat_history = deque(maxlen=6)

# Cache for embeddings
@lru_cache(maxsize=1000)
def get_embeddings(text: str):
    return embedding_model.embed_query(text)

class QuestionRequest(BaseModel):
    question: str
def login_to_huggingface():
    login(token="")
    print("Logged in to Hugging Face")
def load_pdfs_from_folder(folder_path: str) -> List:
    """Load PDFs from the specified folder."""
    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
    documents = []
    for pdf_file in pdf_files:
        loader = PyPDFLoader(pdf_file)
        documents.extend(loader.load())
    return documents

def split_documents(documents: List) -> List:
    """Split documents into chunks."""
    return text_splitter.split_documents(documents)

def initialize_vector_store(documents: List):
    """Initialize and return the vector store with optimized settings."""
    split_docs = split_documents(documents)
    return Chroma.from_documents(
        split_docs,
        embedding_model,
        persist_directory=None,  # Keep in memory
        collection_metadata={
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 100,
            "hnsw:search_ef": 50
        }
    )

def create_rag_system(vector_store):
    """Create the RAG system with optimized retrieval."""
    system_prompt = (
        "You are a helpful assistant answering questions based on the knowledge provided documents while handling a live phone call. "
        "Keep responses brief, clear, and conversational, as if speaking to someone on the phone.\n"
        "Context: {context}\n"
        "Chat History: {chat_history}\n"
        "Current Question: {input}\n"
        "Provide a well-informed response."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 3,
        }
    )

    question_answer_chain = create_stuff_documents_chain(groq_model, prompt)
    return create_retrieval_chain(retriever, question_answer_chain)

# Cache for similar chunks
@lru_cache(maxsize=1000)
def get_similar_chunks(question: str):
    """Get similar chunks from vector store with caching."""
    return vector_store.similarity_search(question, k=3)

@app.on_event("startup")
async def startup_event():
    """Initialize everything at startup."""
    global vector_store, rag_system
    
    print("🔄 Logging in to Hugging Face...")
    login_to_huggingface()
    print("🔄 Loading documents...")
    documents = load_pdfs_from_folder(PDF_FOLDER_PATH)
    if not documents:
        raise Exception("No PDFs found in the folder!")

    print("🔄 Initializing vector store...")
    vector_store = initialize_vector_store(documents)
    
    print("🔄 Creating RAG system...")
    rag_system = create_rag_system(vector_store)
    
    print("✅ Server ready!")

@app.post("/ask")
async def ask_question(request: QuestionRequest):
    """Optimized endpoint for querying the RAG system."""
    t_start = time.time()
    
    # Add question to chat history
    chat_history.append(HumanMessage(content=request.question))
    
    # Get response using cached retrievals
    response = rag_system.invoke({
        "input": request.question,
        "chat_history": list(chat_history)
    })
    
    answer = response.get("answer", "No answer found")
    
    # Add response to chat history
    chat_history.append(AIMessage(content=answer))
    
    return {
        "answer": answer,
        "time_taken": time.time() - t_start
    }

if __name__ == "__main__":
    import uvicorn
    print("🎙 Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8001)