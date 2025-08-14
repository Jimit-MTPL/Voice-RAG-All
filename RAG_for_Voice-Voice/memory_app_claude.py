# import os
# import glob
# from flask import Flask, request, jsonify
# from langchain_community.document_loaders import PyPDFLoader
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_community.vectorstores import Chroma
# from langchain_groq import ChatGroq
# from langchain.chains.retrieval import create_retrieval_chain
# from langchain.prompts import PromptTemplate
# from dotenv import load_dotenv
# from huggingface_hub import login
# from langchain.chains.combine_documents import create_stuff_documents_chain
# from langchain_core.prompts import ChatPromptTemplate
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.memory import ConversationBufferMemory
# import time
# # Initialize Flask app
# app = Flask(__name__)
# def login_to_huggingface():
#     login(token="")
#     print("Logged in to Hugging Face")

# login_to_huggingface()
# # Model and Embedding setup
# BGE_MODEL = "BAAI/bge-small-en-v1.5"
# CHROMA_DB_PATH = "chromadb"
# load_dotenv()

# # Access the API key from the environment
# GROQ_API_KEY = os.getenv('GROQ_API_KEY')
# # Load HuggingFace embeddings
# embedding_model = HuggingFaceEmbeddings(model_name=BGE_MODEL, encode_kwargs={'normalize_embeddings': True})

# # Initialize Groq LLM
# groq_model = ChatGroq(
#     model="llama-3.3-70b-versatile",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
#     api_key=GROQ_API_KEY
# )
# conversation_memories = {}
# # Folder path for PDFs
# PDF_FOLDER_PATH = "pdfs"  # Specify your folder here
# text_splitter = RecursiveCharacterTextSplitter(
#     chunk_size=300,
#     chunk_overlap=30,
#     length_function=len,
#     separators=["\n\n", "\n", ".", " ", ""]
# )
# # Function to load PDFs from a folder
# def load_pdfs_from_folder(folder_path):
#     pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
#     documents = []
#     for pdf_file in pdf_files:
#         loader = PyPDFLoader(pdf_file)
#         documents.extend(loader.load())
#     return documents
# def split_documents(documents):
#     return text_splitter.split_documents(documents)
# # Function to initialize the vector store with PDF documents
# def initialize_vector_store(documents):
#     # Create a Chroma vector store
#     split_docs = split_documents(documents)
#     vector_store = Chroma.from_documents(split_docs, embedding_model, persist_directory=CHROMA_DB_PATH, collection_metadata={"hnsw:space": "cosine"})
#     return vector_store

# # Function to create the RAG system
# def create_rag_system(vector_store, memory):
#     # Define a prompt template for the RAG system
#     system_prompt = (
#     "You are a helpful assistant that can answer questions based on the knowledge provided in documents."
#     "Previous conversation history:{chat_history}" 
#     "Context: {context}"
#     )
#     prompt = ChatPromptTemplate.from_messages(
#     [
#         ("system", system_prompt),
#         ("human", "{input}"),
#     ]
#     )
#     retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})
#     question_answer_chain = create_stuff_documents_chain(groq_model, prompt)
#     rag_chain = create_retrieval_chain(retriever, question_answer_chain)
#     return rag_chain

# # Load PDFs from the specified folder
# documents = load_pdfs_from_folder(PDF_FOLDER_PATH)

# # If no PDFs found, terminate the process
# if not documents:
#     print("No PDFs found in the folder. Exiting...")
#     exit(1)

# # Initialize the vector store with the loaded PDFs
# vector_store = initialize_vector_store(documents)

# # Create the RAG system
# #rag_system = create_rag_system(vector_store)

# @app.route('/ask', methods=['POST'])
# def ask_question():
#     """Query the RAG system with a question"""
#     t_start = time.time()
#     data = request.json
#     question = data.get("question")
#     session_id = data.get("session_id")
#     if not question or not session_id:
#         return jsonify({"error": "Both question and session_id are required"}), 400

#     # Get or create memory for this session
#     if session_id not in conversation_memories:
#         conversation_memories[session_id] = ConversationBufferMemory(
#             return_messages=True,
#             memory_key="chat_history",
#             input_key="input"
#         )
    
#     # Create RAG system with the session's memory
#     memory = conversation_memories[session_id]
#     rag_system = create_rag_system(vector_store, memory)
#     # Get the answer to the question
#     response = rag_system.invoke({"input": question,"chat_history": memory.buffer})
#     memory.save_context({"input": question}, {"output": response["answer"]})
#     answer = response.get("answer", "No answer found")
#     t_end = time.time()
#     t_taken= t_end-t_start
#     return jsonify({"answer": response["answer"], "time": t_taken}), 200

# if __name__ == '__main__':
#     print("🎙 Server is ready to take questions!")
#     # app.run(debug=True)
#     app.run(debug=True, host="0.0.0.0", port=8001)