import os
from flask import Flask, request, jsonify
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader, UnstructuredPDFLoader, PDFPlumberLoader, PDFMinerLoader
from langchain_unstructured import UnstructuredLoader
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
# from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain.schema import Document
from langchain_docling import DoclingLoader
from docling.chunking import HybridChunker
from langchain_docling.loader import ExportType
# from llama_parse import LlamaParse
from llama_cloud_services import LlamaParse

# Initialize Flask app
app = Flask(__name__)
CORS(app)

class SessionState:
    def __init__(self):
        self.md_file_path = None

session_state=SessionState()

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
BGE_MODEL = "BAAI/bge-small-en-v1.5"
CHROMA_DB_PATH = "chromadb"
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
LLAMA_CLOUD_API_KEY = os.getenv('LLAMA_CLOUD_API_KEY')
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

# parser = LlamaParse(
#     api_key= LLAMA_CLOUD_API_KEY,  # can also be set in your env as LLAMA_CLOUD_API_KEY
#     result_type="markdown",  # "markdown" and "text" are available
#     verbose=True,
#     max_timeout=5000
# )

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
# Documents={}
def filter_complex_metadata(doc):
    """Filter out complex metadata while keeping simple types."""
    simple_metadata = {}
    for key, value in doc.metadata.items():
        # Keep only simple data types
        if isinstance(value, (str, int, float, bool)):
            simple_metadata[key] = value
    
    # Keep essential metadata
    simple_metadata = {
        'source': doc.metadata.get('source', ''),
        'page_number': doc.metadata.get('page_number', 1),
        'filename': doc.metadata.get('filename', ''),
        'filetype': doc.metadata.get('filetype', ''),
        'languages': doc.metadata.get('languages', [''])[0] if doc.metadata.get('languages') else '',
        'last_modified': doc.metadata.get('last_modified', ''),
        'category': doc.metadata.get('category', ''),
        'element_id': doc.metadata.get('element_id', '')
    }
    
    return Document(page_content=doc.page_content, metadata=simple_metadata)

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
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    if file_extension == 'pdf':
        # model_lst = load_all_models()
        # full_text, images, out_meta = convert_single_pdf(filepath, model_lst)
        # subfolder_path = save_markdown('marker-output', base_name, full_text, images, out_meta)
        # md_file_path = os.path.join(subfolder_path, f"{base_name}.md")
        # loader = TextLoader(md_file_path)
        # if session_state.md_file_path and not subfolder_path == session_state.md_file_path:
        #     shutil.rmtree(session_state.md_file_path)
        # session_state.md_file_path = subfolder_path
        # -----------------------------------------------------------------------------------------------------
        # loader = PyPDFLoader(filepath)
        # -----------------------------------------------------------------------------------------------------
        # loader = UnstructuredLoader(file_path=filepath, strategy="hi_res", partition_via_api=True, coordinates=False)
        # docs = []
        # # docs = [filter_metadata(doc) for doc in loader.lazy_load()]
        # for doc in loader.lazy_load():
        #     filtered_doc = filter_complex_metadata(doc)
        #     # print(filtered_doc.page_content)
        #     docs.append(filtered_doc)
        # print(docs)
        # output_dir = 'unstructured_output'
        # os.makedirs(output_dir, exist_ok=True)
        # output_md = os.path.join('unstructured_output', f"{base_name}.md")
        # with open(output_md, "w", encoding="utf-8") as f:
        #     for doc in docs:
        #         f.write(doc.page_content + "\n\n")
        # -----------------------------------------------------------------------------------------------------
        docs = []
        loader = DoclingLoader(
            file_path=filepath,
            export_type = ExportType.MARKDOWN,
            # chunker=HybridChunker(tokenizer=BGE_MODEL)
        )
        for doc in loader.lazy_load():
            filtered_doc = filter_metadata(doc)
            docs.append(filtered_doc)
        output_dir = 'docling_output_doc'
        os.makedirs(output_dir, exist_ok=True)
        output_md = os.path.join('docling_output', f"{base_name}.md")
        with open(output_md, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(doc.page_content + "\n------------------------------------------------------------------------------------------------------------\n")
        # print(docs)
        # -----------------------------------------------------------------------------------------------------
        # output_dir = 'llamaparse-output'
        # os.makedirs(output_dir, exist_ok=True) 
        # docs = parser.load_data(filepath)
        # output_md = os.path.join('llamaparse-output', f"{base_name}.md")
        # with open(output_md, 'w') as file:
        #     for doc in docs:
        #         file.write(doc.text + "\n\n")
        # print(docs)
        # -----------------------------------------------------------------------------------------------------
        # loader = PDFMinerLoader(filepath)
        # docs = loader.load()
        # output_dir = 'pdfminer_output'
        # os.makedirs(output_dir, exist_ok=True)
        # output_md = os.path.join('pdfminer_output', f"{base_name}.md")
        # with open(output_md, "w", encoding="utf-8") as f:
        #     for doc in docs:
        #         f.write(doc.page_content + "\n\n")
        # -----------------------------------------------------------------------------------------------------
        # loader = PDFPlumberLoader(filepath)
        # docs = loader.load()
        # output_dir = 'pdfplumber_output'
        # os.makedirs(output_dir, exist_ok=True)
        # output_md = os.path.join('pdfplumber_output', f"{base_name}.md")
        # with open(output_md, "w", encoding="utf-8") as f:
        #     for doc in docs:
        #         f.write(doc.page_content + "\n\n")
        # -----------------------------------------------------------------------------------------------------
    elif file_extension == 'txt':
        loader = TextLoader(filepath, encoding='utf-8')
    elif file_extension == 'csv':
        loader = CSVLoader(filepath)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")
    return docs

def initialize_vector_store(documents):
    split_docs = split_documents(documents)
    # print("-------------split documents below-----------------")
    # print(split_docs)
    #filtered_docs = [filter_complex_metadata(doc) for doc in split_docs]
    vector_store = Chroma.from_documents(split_docs, embedding_model, persist_directory=os.path.basename(CHROMA_DB_PATH), collection_metadata={"hnsw:space": "cosine"})
    return vector_store

def create_rag_system(vector_store):
    system_prompt = (
        # "You are a helpful and professional customer service representative handling phone calls for our application. "
        # "Your primary role is to provide accurate information from our FAQs. Follow these strict guidelines:\n\n"
        # "1. MOST IMPORTANT: When an exact match is found in the FAQs, provide that answer verbatim without any modifications\n"
        # "2. Keep answers concise and to the point\n"
        # "3. Do not add, remove, or modify any information from the FAQ answers\n"
        # "4. If a question is outside of the knowledge base (not covered in FAQs), do not answer it. Instead, respond with:"
        # "   - I am sorry, but I do not have details on that topic."
        # "5. Do not make up or infer information that's not explicitly stated in the FAQs\n"
        # "6. Keep the phone conversation natural but prioritize accuracy over conversation flow\n"
        # "7. If you need clarification to find the right FAQ, ask simple, direct questions\n"
        # "8. End conversations naturally by asking 'Is there anything else I can help you with?' and if not, close with a simple 'Thank you for calling, have a great day!'\n\n"
        # "Context from FAQs: {context}\n"
        # "Chat History: {chat_history}\n"
        # "Current Question: {input}\n"
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
                rag_system = create_rag_system(vector_store)
                
                # if session_state.file_name and not filepath == session_state.file_name:
                #     os.remove(session_state.file_name)
                # session_state.file_name = filepath
                # try:
                #     if session_state.file_name and not filepath == session_state.file_name:
                #         os.remove(session_state.file_name)
                # except Exception as del_error:
                #     print(f"Warning: Failed to delete old file: {str(del_error)}")
                # session_state.file_name = filepath
                # best working logic is below which keeps two latest files and delets all other
                # try:
                #     # Get list of all files in upload folder with their creation times
                #     files_with_times = []
                #     for f in os.listdir(UPLOAD_FOLDER):
                #         f_path = os.path.join(UPLOAD_FOLDER, f)
                #         if os.path.isfile(f_path):
                #             creation_time = os.path.getctime(f_path)
                #             files_with_times.append((f_path, creation_time))
                    
                #     # Sort files by creation time (newest first)
                #     files_with_times.sort(key=lambda x: x[1], reverse=True)
                    
                #     # Remove all but the two most recent files
                #     for old_file, _ in files_with_times[2:]:
                #         try:
                #             os.remove(old_file)
                #             print(f"Removed old file: {old_file}")
                #         except Exception as del_error:
                #             print(f"Warning: Failed to delete old file {old_file}: {str(del_error)}")
                
                # except Exception as cleanup_error:
                #     print(f"Warning: Error during file cleanup: {str(cleanup_error)}")
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

import os
from flask import Flask, send_file, jsonify
import threading

# Define the directory where audio files are stored
save_audio_path = "output_files"
os.makedirs(save_audio_path, exist_ok=True)

# @app.route('/download/<filename>', methods=['GET'])
# def download_file(filename):
#     file_path = os.path.join(save_audio_path, filename)
#     if os.path.exists(file_path):
#         return send_file(file_path, as_attachment=True)
#     else:
#         return jsonify({"error": "File not found"}), 404

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
    app.run(debug=True, host="0.0.0.0", port=8502)