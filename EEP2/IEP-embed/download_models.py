import os
import logging
from sentence_transformers import SentenceTransformer
import torch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def download_models():
    """Pre-download and cache models used by the embedder service"""
    model_name = 'all-MiniLM-L6-v2'
    
    logger.info(f"Starting pre-download of {model_name}")
    
    try:
        # Download and cache the model
        logger.info(f"Downloading {model_name} model...")
        model = SentenceTransformer(model_name)
        
        # Generate a sample embedding to ensure model is fully loaded
        logger.info("Testing model with sample text...")
        text = "This is a test sentence to verify the model works correctly."
        embedding = model.encode([text])
        
        logger.info(f"Model successfully downloaded and tested. Embedding shape: {embedding.shape}")
        logger.info(f"Model is cached and ready to use.")
        
        # Print cache location
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "torch", "sentence_transformers")
        logger.info(f"Model cached at: {cache_dir}")
        
        return True
    except Exception as e:
        logger.error(f"Error downloading model: {str(e)}")
        return False

if __name__ == "__main__":
    # Set environment variables to control model caching and downloading
    os.environ["TRANSFORMERS_OFFLINE"] = "0"  # Allow downloads
    os.environ["TRANSFORMERS_CACHE"] = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    
    logger.info("Starting model download process...")
    success = download_models()
    
    if success:
        logger.info("Model download completed successfully.")
        logger.info("You can now run the embedder.py script without waiting for downloads.")
    else:
        logger.error("Model download failed. Check the error messages above.") 