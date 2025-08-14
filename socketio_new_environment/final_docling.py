import os
from flask import Flask, request, jsonify
from langchain_community.document_loaders import TextLoader, CSVLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain.chains.retrieval import create_retrieval_chain
from dotenv import load_dotenv
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
from langchain.schema import Document
from langchain_docling import DoclingLoader
from docling.chunking import HybridChunker
from langchain_docling.loader import ExportType
from langchain_community.document_transformers import LongContextReorder
from langchain.retrievers import ContextualCompressionRetriever
from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
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
        chat_histories[sid] = deque(maxlen=8)
    return chat_histories[sid]

# Model and Embedding setup
BGE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"#"BAAI/bge-small-en-v1.5"
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
    chunk_size=1024,
    chunk_overlap=20,
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
            
    except Exception as e:
        print(f"Error in reset_vector_store: {str(e)}")
        raise e

def split_documents(documents):
    return text_splitter.split_documents(documents)

def filter_metadata(doc):
    """Remove non-primitive types from metadata."""
    filtered_metadata = {
        key: value for key, value in doc.metadata.items() 
        if isinstance(value, (str, int, float, bool))  # Keep only simple data types
    }
    return Document(page_content=doc.page_content, metadata=filtered_metadata)

def load_document(filepath):
    """Load document based on file extension"""
    file_extension = filepath.split('.')[-1].lower()
    if file_extension == 'pdf':
        docs = []
        loader = DoclingLoader(
            file_path=filepath,
            # export_type=ExportType.MARKDOWN,
            chunker=HybridChunker(tokenizer="sentence-transformers/all-MiniLM-L6-v2")
        )
        for doc in loader.lazy_load():
            filtered_doc = filter_metadata(doc)
            docs.append(filtered_doc)
        pretty_print_docs(docs)
        return docs
    elif file_extension == 'txt':
        loader = TextLoader(filepath, encoding='utf-8')
        return loader.load()
    elif file_extension == 'csv':
        loader = CSVLoader(filepath)
        return loader.load()
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

def initialize_vector_store(documents):
    # split_docs = split_documents(documents)
    # print("-------------split documents below-----------------")
    # pretty_print_docs(split_docs)
    vector_store = Chroma.from_documents(documents, embedding_model, persist_directory=os.path.basename(CHROMA_DB_PATH), collection_metadata={"hnsw:space": "cosine"})
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
        "Context: {context}\n"
        "Chat History: {chat_history}\n"
        "Current Question: {input}\n"
        # "You are a helpful and professional assistant providing accurate information directly and naturally."
        # "Follow these guidelines:\n\n"
        # "1. Answer questions directly and confidently without referencing your sources or mentioning 'the context'.\n"
        # "2. Keep answers concise and focused on the question at hand.\n"
        # "3. If you can reasonably infer something from the available information, do so without highlighting it's an inference.\n"
        # "4. If only partial information is available, provide what you can without mentioning limitations of your knowledge base.\n"
        # # "5. If the question is completely unrelated to your available information, respond with: 'I don't have specific information about that.'\n"
        # "5. If the question is completely outside of the knowledge base (provided context), do not answer it. Instead, respond with: 'I am sorry, but I don't have details on that topic.'\n"
        # "6. Never use phrases like 'based on context', 'context mentions', 'according to the provided information', etc.\n"
        # "7. Speak as if the information is simply something you know, not something you're reading.\n\n"
        # "Context: {context}\n"
        # "Chat History: {chat_history}\n"
        # "Current Question: {input}\n"

        # "You are a helpful and professional assistant providing accurate information based on the provided context."
        # "Follow these guidelines:\n\n"
        # "1. Keep answers concise and focused on the information in the context.\n"
        # "2. If the exact answer isn't in the context but you can reasonably infer it from what is provided, you may do so while noting this is your inference.\n"
        # "3. If only partial information is available in the context, provide what you can and acknowledge the limitations.\n"
        # "4. If the question is completely unrelated to the provided context, respond with: 'I don't have specific information about that in my current knowledge base.'\n"
        # "5. Always extract and use as much relevant information from the context as possible before deciding you can't answer.\n\n"
        # "Context: {context}\n"
        # "Chat History: {chat_history}\n"
        # "Current Question: {input}\n"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 5})
    # ms-marco-TinyBERT-L-2-v2
    compressor = FlashrankRerank(model="ms-marco-MiniLM-L-12-v2")
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=retriever
    )
    question_answer_chain = create_stuff_documents_chain(groq_model, prompt)
    rag_chain = create_retrieval_chain(compression_retriever, question_answer_chain)
    
    return rag_chain, retriever, compression_retriever

# Initialize global variables
vector_store = None
rag_system = None
retriever_simple = None 
retriever_reranker = None
reranker = LongContextReorder()
# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload a single PDF file and update the vector store.
    Removes existing file and recreates the vector store from scratch.
    """
    global vector_store, rag_system, retriever_simple, retriever_reranker
    
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
                reset_vector_store()
                documents = load_document(filepath)
                vector_store = initialize_vector_store(documents)
                rag_system, retriever_simple, retriever_reranker = create_rag_system(vector_store)
                os.remove(filepath)
                return jsonify({
                    "message": "File processed and vector store updated successfully",
                    "processed_file": filename
                }), 200
            except Exception as pe:
                print(f"Processing error: {str(pe)}")
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as cleanup_error:
                    print(f"Warning: Failed to clean up file after processing error: {str(cleanup_error)}")
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
    if not sid:
        return jsonify({"error": "sid is required"}), 400
        
    try:
        if sid in chat_histories:
            del chat_histories[sid]
            return jsonify({"message": f"Chat history cleared for session {sid}"}), 200
        else:
            return jsonify({"message": f"Chat history not found for session {sid}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def pretty_print_docs(docs):
    print(
        f"\n{'-' * 100}\n".join(
            [
                f"Document {i+1}:\n\n{d.page_content}\nMetadata: {d.metadata}"
                for i, d in enumerate(docs)
            ]
        )
    )
@app.route('/ask', methods=['POST'])
def ask_question():
    """Query the RAG system with a question and maintain chat history per session."""
    t_start = time.time()
    
    data = request.json
    question = data.get("question")
    sid = data.get("sid")
    if not question or not sid:
        return jsonify({"error": "Both question and sid are required"}), 400

    if not vector_store or not rag_system:
        return jsonify({"error": "No documents loaded. Please upload a PDF file first."}), 400
    docs_base = retriever_simple.invoke(question)
    print("\n--------------------------------------simple docs------------------------------------------\n")
    pretty_print_docs(docs_base)
    print("\n--------------------------------------reranked docs------------------------------------------\n")
    docs_reranker = retriever_reranker.invoke(question)
    pretty_print_docs(docs_reranker)
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
    # return jsonify({"docs": "retrieved successfully"}), 200

import os
from flask import Flask, send_file, jsonify
import threading

# Define the directory where audio files are stored
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

if __name__ == '__main__':
    print("🎙 Server is ready to take questions!")
    app.run(debug=False, host="0.0.0.0", port=8502)
# ---------------------------------------------------Reference for Flash ReRanker-----------------------------------------------------
# from flashrank import Ranker, RerankRequest

# # Nano (~4MB), blazing fast model & competitive performance (ranking precision).

# ranker = Ranker(max_length=128)

# or 

# # Small (~34MB), slightly slower & best performance (ranking precision).
# ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/opt")

# or 

# # Medium (~110MB), slower model with best zeroshot performance (ranking precision) on out of domain data.
# ranker = Ranker(model_name="rank-T5-flan", cache_dir="/opt")

# or 

# # Medium (~150MB), slower model with competitive performance (ranking precision) for 100+ languages  (don't use for english)
# ranker = Ranker(model_name="ms-marco-MultiBERT-L-12", cache_dir="/opt")

# or 

# ranker = Ranker(model_name="rank_zephyr_7b_v1_full", max_length=1024) # adjust max_length based on your passage length
# ----------------------------------------------------------------------------------------------------------------------------------