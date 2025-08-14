import re
import csv
import os
from typing import List
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from llama_index.core import Settings
from llama_index.llms.huggingface import HuggingFaceLLM
from llama_index.core import VectorStoreIndex
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import MarkdownReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.ingestion import (
    IngestionPipeline
)
from llama_index.core.node_parser import SentenceSplitter
from transformers import AutoTokenizer
from marker.models import load_all_models
from marker.convert import convert_single_pdf
from marker.output import save_markdown
from huggingface_hub import login
import chromadb
from flair.splitter import SegtokSentenceSplitter



# Ensure proper memory allocation for PyTorch
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"


def login_to_huggingface():
    login(token="")
    print("Logged in to Hugging Face")

login_to_huggingface()


model_name = 'meta-llama/Llama-3.2-11B-Vision-Instruct'
tokenizer = AutoTokenizer.from_pretrained(model_name)



def is_table_like(text_block):
    """Heuristically determine if a block of text is structured like a table."""
    lines = text_block.strip().splitlines()
    
    # Check if the majority of lines are similarly structured, e.g., contain delimiters or consistent formatting.
    table_like_lines = [line for line in lines if re.search(r'\s{2,}|\||,|\t', line)]
    
    # Treat as table if more than half the lines look structured
    return len(table_like_lines) > len(lines) * 0.5

def chunk_text_generalized(tokenizer, text, chunk_size=300):
    """Chunk text with tables in mind, keeping table-like structures in one chunk."""
    
    sections = re.split(r'\n{2,}', text)  # Split text into sections by double newlines
    chunks = []
    
    for section in sections:
        if is_table_like(section):
            # Treat entire section as a single chunk if it's table-like
            tokens = tokenizer.encode(section, add_special_tokens=False)
            chunks.append(tokenizer.decode(tokens, skip_special_tokens=True))
        else:
            
            splitter = SegtokSentenceSplitter()
    
            # Split text into sentences
            sentences = splitter.split(section)

            current_chunk = ""

            for sentence in sentences:
                # Add sentence to the current chunk
                if len(current_chunk) + len(sentence.to_plain_string()) <= chunk_size:
                    current_chunk += " " + sentence.to_plain_string()
                else:
                    # If adding the next sentence exceeds max size, start a new chunk
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence.to_plain_string()

        # Add the last chunk if it exists
            if current_chunk:
                chunks.append(current_chunk.strip())
    return chunks
    """
        if is_table_like(section):
            # Treat entire section as a single chunk if it's table-like
            tokens = tokenizer.encode(section, add_special_tokens=False)
            chunks.append(tokenizer.decode(tokens, skip_special_tokens=True))
        else:
            # Otherwise, chunk normally based on token count
            tokens = tokenizer.encode(section, add_special_tokens=False)
            for i in range(0, len(tokens), chunk_size):
                chunk_tokens = tokens[i:i + chunk_size]
                chunks.append(tokenizer.decode(chunk_tokens, skip_special_tokens=True))
    """
    

def create_or_get_vectordb(caller= None):
    # It creates a persistent client with the specified path to store the database.
    chroma_client = chromadb.PersistentClient(path="chroma_db")
    # If the collection "quickstart" does not exist, it creates it

    if caller == "call_from_pipeline":
        try:
            chroma_client.delete_collection(name="qa_db")
        except:
            pass
    
    chroma_collection = chroma_client.get_or_create_collection("qa_db")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)


    if caller == "call_from_chat_engine":
        try:
            atexit.register(lambda: chroma_client.reset())
        except:
            pass   
    #atexit.register(lambda: chroma_client.reset())
    
    return vector_store

def delete_chroma_client(caller= None):
    # It creates a persistent client with the specified path to store the database.
    chroma_client = chromadb.PersistentClient(path="chroma_db")
    atexit.register(lambda: chroma_client.reset())

def new_index(vector_store, embed_model):
    #create a new VectorStoreIndex using the provided vector store and embedding model
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )
    return index

def create_chat_engine():
        index = new_index(create_or_get_vectordb(caller="call_from_chat_engine"), embed_model())
        query_engine = index.as_chat_engine(
        chat_mode="context",
        system_prompt= f"""
        You are tasked with generating high-quality, meaningful question-answer pairs from the given context. 
        Each question should cover a unique point. Avoid direct references (e.g., "according to the text") and do not include any emojis in either the questions or answers.
    
        Format:
        Question: [Insert question here]
        Answer: [Insert answer here]
    
        Ensure:
        1. Questions address different key details.
        2. Answers are detailed and context-rich.
        3. Language is formal and free of emojis or informal symbols.
        """
        )
        return query_engine
        
def interact_with_llm(customer_query):
        chat_engine = create_chat_engine()
        AgentChatResponse = chat_engine.chat(customer_query)
        answer = AgentChatResponse.response
        return answer


def embed_model():
    embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5", cache_folder="cache_model")
    return embed_model

def create_or_load_pipeline():
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(),
            embed_model(),
        ],
        vector_store=create_or_get_vectordb(caller="call_from_pipeline"),
        docstore=SimpleDocumentStore()
    )
    pipeline.persist("pipeline_store")
    pipeline.load("pipeline_store")

    return pipeline

def data_ingestion(query):

    fname = "/workspace/QA_multimodal/pdf2.pdf"
    base_fname = os.path.splitext(os.path.basename(fname))[0]
    model_lst = load_all_models()
    full_text, images, out_meta = convert_single_pdf(fname, model_lst)

    filtered_text = re.sub(r'!\[\d+_image_\d+\.png\]\(\d+_image_\d+\.png\)', '', full_text)
    # Assume tables are identifiable as structured text within `full_text`
    text_sections = re.split(r'\n\n+', filtered_text)
    full_text_str = "\n\n".join(text_sections)
    removed_blank_line = re.sub(r'(?<!\|)(\n{2,})(?!\|)', '\n', full_text_str)
    process_text = re.sub(r'(?:^|\n)(?<!\n\n)(#{1,6}(?:\s+)?[^\n]*)', r'\n\n\1\n', removed_blank_line)
    processed_text = re.sub(r'(#+ .+)\n{2,}', r'\1\n', process_text)
    
    # Split document into chunks
    fname = os.path.basename(fname)
    subfolder_path = save_markdown('marker-output', fname, processed_text, images, out_meta)
    
    input_file = os.path.join(subfolder_path, f"{base_fname}.md")
    parser = MarkdownReader()
    file_extractor = {".md": parser}
    reader = SimpleDirectoryReader(
                input_files=[input_file],
                file_extractor=file_extractor
            )

        # Load the content from the file
    documents = reader.load_data()
    qa_list = []

    txt_dir = "/workspace/QA_multimodal/QA_WITH_CHUNKS"
    os.makedirs(txt_dir, exist_ok=True)
    txt_file_path = os.path.join(txt_dir, f"{base_fname}.txt")
    

    with open(txt_file_path, mode='w', encoding='utf-8') as txt_file:
        for document in documents:
        # Process each chunk through the pipeline
            chunks = chunk_text_generalized(tokenizer, text=document.text, chunk_size=600)
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1} of file {input_file}...")
                print(f"Chunk {i+1} content:\n{chunk}\n")
            
            # Save the chunk content in the text file
                txt_file.write(f"--- Chunk {i+1} ---\n")
                txt_file.write(chunk.strip() + "\n\n")
            
            # Convert the chunk into a document format
                chunk_document = type(document)(text=chunk)
                pipeline = create_or_load_pipeline()
            
            # Pass the chunked document through the pipeline
                nodes = pipeline.run(documents=[chunk_document])
                print(f"Ingested {len(nodes)} Nodes from chunk {i+1}")

            # Interact with LLM for the processed chunk
                print(f"Running query on chunk {i+1}...")
                output = interact_with_llm(query)
                print(f"Response for chunk {i+1}: {output}")

            # Extract Q&A pairs from the LLM output
                qa_pairs = []
                question, answer = None, None
                for line in output.split("\n"):
                    if re.match(r'^(Question:|Q:)', line):
                        if question and answer:
                            qa_pairs.append((question, answer))
                        question = re.sub(r'^(Question:|Q:)', '', line).strip()
                        answer = None
                    elif re.match(r'^(Answer:|A:)', line):
                        answer = re.sub(r'^(Answer:|A:)', '', line).strip()
                    elif answer is not None:
                        answer += " " + line.strip()
                if question and answer:
                    qa_pairs.append((question, answer))
                qa_list.extend(qa_pairs)

            # Write Q&A pairs for the chunk to the text file
                txt_file.write("--- Extracted Q&A Pairs ---\n")
                for question, answer in qa_pairs:
                    txt_file.write(f"Question: {question}\n")
                    txt_file.write(f"Answer: {answer}\n\n")
                txt_file.write("-" * 40 + "\n\n")  # Separator for readability
            
                print("\n--- Extracted Q&A Pairs ---\n")
                for question, answer in qa_pairs:
                    print(f"Question: {question}\nAnswer: {answer}\n")

    print(f"Q&A pairs with chunks saved to {txt_file_path}")



def main():
    # Initialize model and tokenizer
    
    device='cuda'
    print("Initializing Model...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16
    ).to(device)
    
    # Set up model settings for LlamaIndex with Hugging Face LLM
    Settings.llm = HuggingFaceLLM(
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=4000,
        context_window=8192,
        generate_kwargs={
            "temperature": 0.3,  # Adjust this value between 0.0 and 1.0
            "do_sample": True   # Required for temperature to have an effect
        }
    )
    model.eval()  # Set model to evaluation mode

    # Define a query and ingest data
    query = """
    Generate a response based on the provided prompt.
    """
    data_ingestion(query)

# Execute main function if the script is run directly
if __name__ == "__main__":
    main()












        

