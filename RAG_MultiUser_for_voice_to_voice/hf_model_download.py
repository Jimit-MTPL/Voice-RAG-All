import os
from huggingface_hub import snapshot_download
from transformers import AutoModel, AutoTokenizer

def download_model(model_name="BAAI/bge-small-en-v1.5", save_dir="models"):
    """
    Download model and tokenizer from HuggingFace and save to specified directory
    
    Args:
        model_name (str): Name of the model on HuggingFace
        save_dir (str): Directory to save the model
    """
    try:
        # Create the save directory if it doesn't exist
        model_dir = os.path.join(save_dir, model_name.split('/')[-1])
        os.makedirs(model_dir, exist_ok=True)
        
        print(f"Downloading model {model_name} to {model_dir}...")
        
        # Download the model files
        snapshot_download(
            repo_id=model_name,
            local_dir=model_dir,
            ignore_patterns=["*.safetensors", "*.bin"] 
        )
        
        # Download and save the model
        model = AutoModel.from_pretrained(model_name)
        model.save_pretrained(model_dir)
        print(f"Model saved to {model_dir}")
        
        # Download and save the tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        tokenizer.save_pretrained(model_dir)
        print(f"Tokenizer saved to {model_dir}")
        
        print(f"\nModel and tokenizer successfully downloaded and saved to: {model_dir}")
        print(f"You can now use this local path in your applications")
        
    except Exception as e:
        print(f"Error downloading model: {str(e)}")
        raise

if __name__ == "__main__":
    # You can specify a different save directory here
    download_model(save_dir="models")