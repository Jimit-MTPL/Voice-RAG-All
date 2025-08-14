from flask import Flask, request, jsonify
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    ServiceContext,
    set_global_service_context
)
from llama_index.vector_stores.chroma import ChromaVectorStore

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq
from llama_index.core.memory import ChatMemoryBuffer
import chromadb
import os
from dotenv import load_dotenv
from huggingface_hub import login
from llama_index.core import Settings
import time
app = Flask(__name__)

# Load environment variables
load_dotenv()
def initialize_rag():
    # Initialize Groq LLM
    llm = Groq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile"
    )
    login(token="")
    print("Logged in to Hugging Face")
    # Initialize the embedding model
    embed_model = HuggingFaceEmbedding(
        model_name="BAAI/bge-small-en-v1.5"
    )
    Settings.llm = llm
    Settings.embed_model = embed_model
    # Create service context
    # service_context = ServiceContext.from_defaults(
    #     llm=llm,
    #     embed_model=embed_model,
    # )
    # set_global_service_context(service_context)

    # Initialize ChromaDB
    db = chromadb.PersistentClient(path="chroma_db")
    chroma_collection = db.get_or_create_collection("documents")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    # Load documents from the PDF directory
    documents = SimpleDirectoryReader(
        input_dir="pdf_documents",
        filename_as_id=True
    ).load_data()

    # Create vector store index
    index = VectorStoreIndex.from_documents(
        documents,
        vector_store=vector_store,
        embed_model=embed_model
    )

    # Initialize chat engine with memory
    memory = ChatMemoryBuffer.from_defaults(token_limit=1500)
    chat_engine = index.as_chat_engine(
        chat_mode="condense_plus_context",
        memory=memory,
        verbose=True
    )

    return chat_engine

# Initialize the RAG system
try:
    chat_engine = initialize_rag()
except Exception as e:
    print(f"Error initializing RAG system: {e}")
    chat_engine = None

# Store chat sessions
chat_sessions = {}

@app.route('/chat', methods=['POST'])
def chat():
    t_start= time.time()
    if not chat_engine:
        return jsonify({"error": "RAG system not initialized"}), 500

    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "No message provided"}), 400

        # Get session ID from request or create new one
        session_id = data.get('session_id', 'default')
        if session_id not in chat_sessions:
            chat_sessions[session_id] = initialize_rag()

        message = data['message']
        response = chat_sessions[session_id].chat(message)
        t_end = time.time()
        t_taken= t_end - t_start
        return jsonify({
            "TIME": t_taken,
            "session_id": session_id,
            "message": message,
            "response": str(response),
            "sources": [
                {
                    "file": node.metadata.get("file_name", "Unknown"),
                    "text": node.get_content()
                }
                for node in response.source_nodes
            ]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8002)