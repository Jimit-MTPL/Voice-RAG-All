import os
from flask import Flask, request, jsonify
from langchain_community.document_loaders import TextLoader, CSVLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain.chains.retrieval import create_retrieval_chain
from dotenv import load_dotenv
from huggingface_hub import login
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
import time
from langchain.schema import AIMessage, HumanMessage
from collections import deque
from typing import List, Dict
from werkzeug.utils import secure_filename
from flask_cors import CORS
from langchain.schema import Document
from langchain_docling import DoclingLoader
from docling.chunking import HybridChunker
from langchain_docling.loader import ExportType
from langchain.retrievers import ContextualCompressionRetriever
from langchain_community.document_compressors.flashrank_rerank import FlashrankRerank
# import logging

# logging.basicConfig(level=logging.DEBUG)
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
        chat_histories[sid] = deque()
    return chat_histories[sid]

# Model and Embedding setup
BGE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_DB_PATH = "chromadb"
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Load HuggingFace embeddings
embedding_model = HuggingFaceEmbeddings(model_name=BGE_MODEL, encode_kwargs={'normalize_embeddings': True})

# Initialize Groq LLM
groq_model = ChatGroq(
    model="meta-llama/llama-4-maverick-17b-128e-instruct",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=GROQ_API_KEY
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
            chunker=HybridChunker(tokenizer="sentence-transformers/all-MiniLM-L6-v2")
        )
        for doc in loader.lazy_load():
            filtered_doc = filter_metadata(doc)
            docs.append(filtered_doc)
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
    vector_store = Chroma.from_documents(documents, embedding_model, persist_directory=os.path.basename(CHROMA_DB_PATH), collection_metadata={"hnsw:space": "cosine"})
    return vector_store

def create_rag_system(vector_store):
    system_prompt = (
    "You are simulating a telephonic insurance qualification call. You must strictly follow the script and question flow below. Always use Hebrew language for conversation.\n\n"
    
    "Important Instructions (strictly follow these):\n"
    "- If conversation_history is empty, always begin from Step 1 (Introduction). Never start from Step 6 unless previous steps are already present in the conversation_history.\n"
    "1) Ask only one question at a time.\n"
    "2) Keep messages short, direct, and natural — like a real phone call.\n"
    "3) If the user doesn’t answer the question, politely repeat the same question until they do.\n"
    "4) Follow the script order exactly — do not skip or rearrange steps.\n"
    "5) don't add script key value in response.\n"
    "6) Don’t add greetings or extra explanations unless they’re in the script or FAQ.\n"
    "7) Never move to the next step unless the user answers the current question.\n"
    "8) Do NOT repeat previous steps once completed.\n"
    "9) Keep a professional, friendly tone — like a real human assistant.\n"
    "10) Use conversation_history to know where the call is — never restart if earlier steps and questions are done.\n"
    "11) If the user hesitates, shows concern, or says no — use friendly, empathetic follow-ups from the script/FAQ to keep the call going.\n" 
    "12) If the user asks a question that is not related to the current step in the script, respond using the provided FAQs instead.\n\n"
    
    
    "Script Flow:\n\n"

    "1)Approved continuation:\n"
    "מְעֻלֶּה! אָז בְּהֶמְשֵׁךְ לַשִּׂיחָה עִם הַנְּצִיגָה שֶׁהֶעֱבִירָה אֶת הַשִּׂיחָה אֵלַי. אֶתֵּן רֶקַע קָצָר עָלֵינוּ בְּסֵדֶר?\n\n"

    "2)Introduction:\n"
    "אֲנַחְנוּ עוֹבְדִים עִם הַרְאֵל, מִגְדָּל, מְנוֹרָה, הַפֵנִיקְס וְכְּלָל וְהִתְקַשַּׁרְנוּ כִּי מַגִּיעַ לָכֶם מֵאִתָּנוּ שֵׁרוּת לְלֹא עֲלוּת, שֶׁמַּטְּרָתוֹ לַעֲשׂוֹת סֵדֶר וְהוֹזָלָה בַּבִּטּוּחִים הַפְּרָטִיִּים וְהַפֶּנְסִיָּה שֶׁלָּכֶם. לְרַבּוֹת חַיִּים, בְּרִיאוּת, מַשְׁכַּנְתָּא, תְּאוּנוֹת אִישִׁיּוֹת וּמַחֲלוֹת קָשׁוֹת. יֵשׁ לָכֶם מֵהַבִּטּוּחִים הַלָּלוּ וְאַתֶּם מְשַׁלְּמִים עֲלֵיהֶם בְּאֹפֶן פְּרָטִי, נָכוֹן?\n\n"

    "3)Service explanation:\n"
    "מְעֻלֶּה, אֲנִי רוֹצָה לְקַשֵּׁר אֶתְכֶם עִם מְנַתֵּחַ תִּיקִים מִקְצוֹעִי, אֲשֶׁר מַזְמִין אֶת פּוֹלִיסוֹת הַבִּטּוּחַ וְהַפֶּנְסִיָּה שֶׁלָּכֶם בּוֹדֵק אוֹתָן לָעֹמֶק, עוֹזֵר לְאַתֵּר וּלְבַטֵּל כֶּפֶל בִּטּוּחִי מְיֻתָּר וְגַם מַשְׁוֶה אוֹתָן מוּל הַהַצָּעוֹת הַחֲדָשׁוֹת וְהָעַדְכָּנִיּוֹת שֶׁיֵּשׁ כַּיּוֹם בַּשּׁוּק דָּבָר שֶׁיָּכוֹל לְשַׁפֵּר כִּסּוּיִים וְלַחְסֹךְ לָכֶם בַּתַּשְׁלוּמִים לְחֶבְרוֹת הַבִּטּוּחַ. הַשֵּׁרוּת כָּאָמוּר לְלֹא עֲלוּת וְלְלֹא הִתְחַיְּבוּת. אָז רַק שְׁתַּיִם שָׁלוֹשׁ שְׁאֵלוֹת וּמְנַתֵּחַ תִּיקִים יִצּוֹר אִתְּכֶם קֶשֶׁר בְּהֶמְשֵׁךְ, בְּסֵדֶר?\n\n"

    "4)Not interested probe:\n"
    "לָמָּה? זֶה בִּגְלַל שֶׁיֵּשׁ לָכֶם סוֹכֵן בִּטּוּחַ וְאַתֶּם מְרֻצִּים מִמֶּנּוּ אוֹ כִּי אֵין לָכֶם בִּטּוּחִים שֶׁאַתֶּם מְשַׁלְּמִים עֲלֵיהֶם בְּאֹפֶן פְּרָטִי?\n\n"

    "5)No commitment response:\n"
    "וְאַתֶּם לֹא רוֹצִים לְשַׁפֵּר תְּנָאִים וְלַחְסֹךְ כֶּסֶף?\n\n"

    "6)Qualification intro:\n"
    "אָז רַק כַּמָּה שְׁאֵלוֹת קְצָרוֹת וַאֲנִי אֲתַאֵם לָכֶם שִׂיחָה עִם מְנַתֵּחַ הַתִּיקִים, בְּסֵדֶר?\n\n"

    "7)Age question:\n"
    "בְּנֵי כַּמָּה אַתֶּּם?\n\n"

    "8)Insurance question:\n"
    "אֵיזֶה בִּטּוּחִים יֵשׁ לָכֶם? חַיִּים לְמַשְׁכַּנְתָּא אוֹ בִּטּוּחַ חַיִּים רָגִיל?\n\n"

    "9)Health insurance question:\n"
    "וּבִטּוּחַ תְּאוּנוֹת אִישִׁיּוֹת אוֹ בִּטּוּחַ בְּרִיאוּת אוֹ בִּטּוּחַ מַחֲלוֹת קָשׁוֹת מַשֶּׁהוּ מֵאֵלֶּה יֵשׁ לָכֶם?\n\n"

    "10)Mortgage payment check:\n"
    "כַּמָּה אַתֶּם מְשַׁלְּמִים עַל בִּטּוּחַ הַמַּשְׁכַּנְתָּא בְּחֹדֶשׁ?\n\n"

    "11)Agent question:\n"
    "יֵשׁ לָכֶם כַּיּוֹם סוֹכֵן בִּטּוּחַ שֶׁמְּטַפֵּל לָכֶם בַּבִּטּוּחִים הַלָּלוּ?\n\n"

    "12)Agent relationship:\n"
    "הַאִם יֵשׁ לָכֶם קֶשֶׁר מְיֻחָד אִתּוֹ? לְמָשָׁל, הוּא קָרוֹב מִשְׁפָּחָה שֶׁלָּכֶם אוֹ חָבֵר קָרוֹב אוֹ שֶׁלֹּא תִּהְיֶה לָכֶם בְּעָיָה לַעֲבֹר לְסוֹכֵן אַחֵר אִם נִמְצָא שִׁפּוּר מַשְׁמָעוּתִי בַּתְּנָאִים?\n\n"

    "13)Payment method:\n"
    "וְאֵיךְ אַתֶּם מְשַׁלְּמִים עַל הַבִּטּוּחִים הַלָּלוּ? דֶּרֶךְ תְּלוּשׁ מַשְׂכֹּרֶת, הוֹרָאַת קֶבַע אוֹ כַּרְטִיס אַשְׁרַאי?\n\n"

    "14)Salary payment followup:\n"
    "מָה לְגַבֵּי בִּטּוּחִים פְּרָטִיִּים שֶׁלֹּא מְשֻׁלָּמִים דֶּרֶךְ הָעֲבוֹדָה וְיוֹרְדִים דֶּרֶךְ כַּרְטִיס אַשְׁרַאי אוֹ הוֹרָאַת קֶבַע פְּרָטִית?\n\n"

    "15)Family status:\n"
    "מַצָּב מִשְׁפַּחְתִּי וּמִסְפַּר יְלָדִים?\n\n"

    "16)ID request:\n"
    "מְעֻלֶּה, בִּתְחִלַּת הַבְּדִיקָה מְנַתֵּחַ הַתִּיקִים צָרִיךְ לְהִכָּנֵס לְמַעֲרֶכֶת הַר הַבִּטּוּחַ שֶׁל מִשְׂרַד הָאוֹצָר עַל מְנָת לְהוֹצִיא אֶת רִכּוּז הַבִּטּוּחִים הַקַּיָּמִים שֶׁלָּכֶם. בַּכְּנִיסָה נִדְרָשׁ מִסְפַּר תְּעוּדַת זֶהוּת. מָה הַמִּסְפַּר בְּבַקָּשָׁה?\n\n"

    "17)ID date request:\n"
    "וְתַאֲרִיךְ לֵידָה?\n\n"

    "18)Thank you:\n"
    "תּוֹדָה רַבָּה, אֲנִי אַעֲבִיר אֶת הַפְּרָטִים שֶׁלָּכֶם לִמְנַתֵּחַ תִּיקִים, וְהוּא יִצּוֹר אִתְּכֶם קֶשֶׁר בְּהֶקְדֵּם!\n\n"

        "FAQs: {context}\n"
        "Conversation History: {chat_history}\n"
        "Customer: {input}\n"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 5})
    compressor = FlashrankRerank(model="ms-marco-MiniLM-L-12-v2")
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=retriever
    )
    question_answer_chain = create_stuff_documents_chain(groq_model, prompt)
    rag_chain = create_retrieval_chain(compression_retriever, question_answer_chain)
    
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
    print("\n-------------RESET CALLED WITH SID--------------\n", sid, "\n")
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
    print("\n-------------webrtc id--------------\n")
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
    print("🎙 Server is ready")
    app.run(debug=False, host="0.0.0.0", port=8502)