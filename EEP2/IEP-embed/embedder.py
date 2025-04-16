from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
import numpy as np
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import io
import base64
from sklearn.decomposition import PCA
import uuid
import os

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load the SentenceTransformer model (e.g., "all-MiniLM-L6-v2")
MODEL_NAME = 'all-MiniLM-L6-v2'
model = None  # Will be loaded on first request

# Create a directory for storing embedding visualizations
VISUAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'visualizations')
os.makedirs(VISUAL_DIR, exist_ok=True)

@app.route("/embed", methods=["POST"])
def embed_text():
    global model
    
    # Lazy loading of the model
    if model is None:
        try:
            logger.info(f"Loading model {MODEL_NAME}...")
            model = SentenceTransformer(MODEL_NAME)
            logger.info(f"Model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return jsonify({"error": f"Failed to load model: {str(e)}"}), 500
    
    data = request.get_json()
    if not data or "text" not in data:
        logger.error("Missing 'text' parameter in request")
        return jsonify({"error": "Missing 'text' parameter"}), 400

    text = data["text"]
    
    # Check if text is too long and truncate if necessary
    max_chars = 10000  # Reduced from 15000 to avoid memory issues
    if len(text) > max_chars:
        logger.warning(f"Text too long ({len(text)} chars), truncating to {max_chars} chars")
        text = text[:max_chars] + "... [TRUNCATED]"
    
    try:
        # Break text into sentences for sentence-level embeddings
        sentences = split_into_sentences(text)
        
        # Limit number of sentences for efficiency
        max_sentences = 50
        if len(sentences) > max_sentences:
            logger.warning(f"Too many sentences ({len(sentences)}), limiting to {max_sentences}")
            sentences = sentences[:max_sentences]
        
        # Generate embeddings for the full text
        logger.info(f"Generating embedding for text of length {len(text)} with {len(sentences)} sentences")
        full_embedding = model.encode([text], show_progress_bar=False)[0]
        
        # Generate sentence embeddings only if we have a reasonable number of sentences
        if sentences and len(sentences) <= max_sentences:
            sentence_embeddings = model.encode(sentences, show_progress_bar=False)
            logger.info(f"Generated embeddings for {len(sentences)} sentences")
        else:
            sentence_embeddings = []
            logger.info("Skipping sentence embeddings due to size constraints")
        
        # Create visualization of the embedding (if we have sentence embeddings)
        visualization = create_embedding_visualization(full_embedding, sentence_embeddings, sentences)
        
        # Calculate embedding statistics
        stats = calculate_embedding_statistics(full_embedding)
        
        # Convert to Python lists for JSON serialization
        full_embedding_list = full_embedding.tolist()
        
        # Create a truncated version for display
        display_embedding = []
        if len(full_embedding_list) > 20:
            display_embedding = full_embedding_list[:20] + ["..."]
        else:
            display_embedding = full_embedding_list
            
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        return jsonify({"error": str(e)}), 500

    # Get the current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Return the embedding along with additional visualization data
    return jsonify({
        "embedding": full_embedding_list,
        "display_embedding": display_embedding,
        "dimensions": len(full_embedding_list),
        "model": MODEL_NAME,
        "timestamp": timestamp,
        "statistics": stats,
        "visualization": visualization,
        "num_sentences": len(sentences) if sentences else 0
    }), 200

def split_into_sentences(text):
    """Split text into sentences using basic rules"""
    import re
    # Simple sentence splitting - will work for most cases
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Filter out empty sentences and very short ones
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    # Limit to a reasonable number of sentences to avoid memory issues
    return sentences[:100] if len(sentences) > 100 else sentences

def create_embedding_visualization(full_embedding, sentence_embeddings, sentences):
    """Create visualizations for embedding"""
    try:
        # Skip if we don't have enough sentence embeddings
        if len(sentence_embeddings) < 3:
            logger.info("Not enough sentences for visualization")
            return {"error": "Not enough sentences for visualization"}
        
        # Generate a unique ID for this visualization
        vis_id = str(uuid.uuid4())[:8]
        
        # Limit the number of sentences for visualization to improve performance
        max_vis_sentences = 30  # Maximum number of sentences to visualize
        if len(sentence_embeddings) > max_vis_sentences:
            logger.info(f"Limiting visualization to {max_vis_sentences} sentences")
            # Sample sentences evenly to get a representative subset
            indices = np.linspace(0, len(sentence_embeddings) - 1, max_vis_sentences, dtype=int)
            sentence_embeddings_vis = sentence_embeddings[indices]
        else:
            sentence_embeddings_vis = sentence_embeddings
        
        # Create a 2D PCA projection
        plt.figure(figsize=(8, 6))  # Reduced size for better performance
        
        # Apply PCA to reduce dimensionality to 2D
        pca = PCA(n_components=2)
        all_embeddings = np.vstack([sentence_embeddings_vis, [full_embedding]])
        points = pca.fit_transform(all_embeddings)
        
        # Plot sentence embeddings
        plt.scatter(points[:-1, 0], points[:-1, 1], alpha=0.7, label="Sentences")
        
        # Plot full document embedding with a different color and size
        plt.scatter(points[-1, 0], points[-1, 1], color='red', s=100, label="Full Document")
        
        # Add labels and legend
        plt.title("2D PCA Projection of Embeddings")
        plt.xlabel("Principal Component 1")
        plt.ylabel("Principal Component 2")
        plt.legend()
        plt.tight_layout()
        
        # Save to memory buffer with lower DPI for smaller file size
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=80)
        plt.close()
        buf.seek(0)
        
        # Encode as base64
        pca_vis = base64.b64encode(buf.read()).decode('utf-8')
        
        # Save to file for debugging (only if VISUAL_DIR exists)
        try:
            if os.path.exists(VISUAL_DIR):
                vis_file = os.path.join(VISUAL_DIR, f"embed_vis_{vis_id}.png")
                with open(vis_file, 'wb') as f:
                    f.write(base64.b64decode(pca_vis))
        except Exception as e:
            logger.warning(f"Could not save visualization to file: {str(e)}")
        
        return {
            "pca_visualization": pca_vis,
            "id": vis_id
        }
        
    except Exception as e:
        logger.error(f"Error creating visualization: {str(e)}")
        return {"error": str(e)}

def calculate_embedding_statistics(embedding):
    """Calculate statistics for the embedding vector"""
    try:
        stats = {
            "min": float(np.min(embedding)),
            "max": float(np.max(embedding)),
            "mean": float(np.mean(embedding)),
            "median": float(np.median(embedding)),
            "std": float(np.std(embedding)),
            "l2_norm": float(np.linalg.norm(embedding))
        }
        return stats
    except Exception as e:
        logger.error(f"Error calculating statistics: {str(e)}")
        return {}

@app.route("/health", methods=["GET"])
def health_check():
    global model
    model_status = "loaded" if model is not None else "not_loaded"
    return jsonify({
        "status": "healthy", 
        "service": "iep-embed", 
        "model": MODEL_NAME,
        "model_status": model_status
    }), 200

if __name__ == "__main__":
    logger.info(f"Starting IEP-embed service with model {MODEL_NAME}")
    app.run(host="0.0.0.0", port=5004, debug=True)
