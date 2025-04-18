from flask import Flask, request, jsonify
import os
import logging
import platform
from sentence_transformers import SentenceTransformer
import numpy as np
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, JSON, LargeBinary, Text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.sql import func
from dotenv import load_dotenv
import uuid
import matplotlib.pyplot as plt
import io
import base64
from sklearn.decomposition import PCA
import weaviate

# Load environment variables
load_dotenv()

# Define a function to split text into chunks
def split_text(text, chunk_size=1000, overlap=100):
    """Split text into overlapping chunks of a specified size."""
    if not text or not isinstance(text, str):
        logger.warning(f"Invalid text provided for splitting: {type(text)}")
        return []
        
    chunks = []
    if len(text) <= chunk_size:
        logger.info(f"Text length ({len(text)}) is less than or equal to chunk size ({chunk_size}), returning as single chunk")
        return [text]
        
    logger.info(f"Splitting text of length {len(text)} into chunks of size {chunk_size} with overlap {overlap}")
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if len(chunk) < 50:  # Skip very small chunks at the end
            logger.debug(f"Skipping small chunk of size {len(chunk)}")
            continue
        chunks.append(chunk)
    
    logger.info(f"Created {len(chunks)} chunks from text")
    return chunks

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy
Base = declarative_base()

class Embedding(Base):
    """Schema for document embeddings"""
    __tablename__ = 'embeddings'
    
    id = Column(String, primary_key=True)
    document_id = Column(String, nullable=False)
    text_chunk = Column(Text, nullable=False)
    embedding = Column(LargeBinary, nullable=False)  # Store numpy array as binary
    embedding_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=func.now())

# Initialize database
db_path = os.path.join(os.path.dirname(__file__), 'iep_embed.db')
engine = create_engine(
    f'sqlite:///{db_path}',
    echo=True
)
Base.metadata.create_all(engine)
Session = scoped_session(sessionmaker(bind=engine))

# Initialize the embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize Weaviate client (optional)
WEAV_URL = os.environ.get('WEAV_URL', 'http://localhost:8080')
WEAV_STARTUP_TIMEOUT = int(os.environ.get('WEAV_STARTUP_TIMEOUT', '20'))  # Increased timeout

# Attempt to connect to Weaviate
weav = None
# Check if we're running on Windows
if platform.system() == "Windows":
    logger.info("Windows detected - Weaviate embedded is not supported on Windows. Using SQLite only.")
else:
    try:
        logger.info(f"Attempting to connect to Weaviate at {WEAV_URL}")
        
        # Connect with a longer timeout
        weav = weaviate.Client(
            url=WEAV_URL
        )
        logger.info(f"Connected to Weaviate at {WEAV_URL}")
        
        # Create schema if it doesn't exist
        if not weav.schema.exists("DocumentChunk"):
            document_chunk_schema = {
                "class": "DocumentChunk",
                "description": "A chunk of text from a document with its embedding",
                "vectorizer": "none",  # We provide vectors manually
                "properties": [
                    {
                        "name": "document_id",
                        "dataType": ["string"],
                        "description": "The ID of the document this chunk belongs to"
                    },
                    {
                        "name": "user_id",
                        "dataType": ["string"],
                        "description": "The ID of the user who owns this document"
                    },
                    {
                        "name": "text",
                        "dataType": ["text"],
                        "description": "The text content of this chunk"
                    },
                    {
                        "name": "chunk_index",
                        "dataType": ["int"],
                        "description": "The position of this chunk in the document"
                    },
                    {
                        "name": "timestamp",
                        "dataType": ["date"],
                        "description": "When this chunk was created"
                    }
                ]
            }
            weav.schema.create_class(document_chunk_schema)
            logger.info("Created DocumentChunk schema in Weaviate")
    except Exception as e:
        logger.error(f"Failed to initialize Weaviate: {str(e)}", exc_info=True)
        weav = None
        logger.warning("Continuing without Weaviate support. Using SQLite only.")

def save_embedding(document_id: str, text_chunk: str, embedding_array: np.ndarray, metadata: dict = None):
    """Save embedding to database"""
    embedding_id = str(uuid.uuid4())
    session = Session()
    try:
        embedding = Embedding(
            id=embedding_id,
            document_id=document_id,
            text_chunk=text_chunk,
            embedding=embedding_array.tobytes(),  # Convert numpy array to bytes
            embedding_metadata=metadata or {}
        )
        session.add(embedding)
        session.commit()
        
        # Also save to Weaviate if available
        if weav:
            try:
                # Extract user_id from metadata
                user_id = metadata.get('user_id', 'unknown')
                
                # Store in Weaviate
                weav.data_object.create(
                    data_object={
                        "document_id": document_id,
                        "user_id": user_id,
                        "text": text_chunk,
                        "chunk_index": 0,  # Default
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    class_name="DocumentChunk",
                    uuid=embedding_id,
                    vector=embedding_array.tolist()
                )
                logger.info(f"Saved embedding {embedding_id} to Weaviate")
            except Exception as e:
                logger.error(f"Error saving to Weaviate (continuing with SQLite only): {str(e)}")
        
        # Return a dictionary instead of the SQLAlchemy object
        return {
            'id': embedding_id,
            'document_id': document_id,
            'text_chunk': text_chunk,
            'metadata': metadata or {}
        }
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_embedding(document_id: str):
    """Retrieve embeddings for a document"""
    # Try to fetch from Weaviate first if available
    if weav:
        try:
            logger.info(f"Fetching embeddings for document {document_id} from Weaviate")
            
            # Retrieve document chunks from Weaviate
            result = weav.query.get(
                "DocumentChunk", 
                ["document_id", "text", "user_id"]
            ).with_where({
                "path": ["document_id"],
                "operator": "Equal",
                "valueString": document_id
            }).with_additional(["vector"]).do()
            
            # Check if we found any embeddings
            if result and "data" in result and "Get" in result["data"] and "DocumentChunk" in result["data"]["Get"]:
                chunks = result["data"]["Get"]["DocumentChunk"]
                if chunks:
                    logger.info(f"Found {len(chunks)} embeddings in Weaviate for document {document_id}")
                    embeddings = []
                    for chunk in chunks:
                        embedding_vector = np.array(chunk["_additional"]["vector"])
                        embeddings.append({
                            'id': chunk["id"] if "id" in chunk else str(uuid.uuid4()),
                            'document_id': document_id,
                            'text_chunk': chunk["text"],
                            'embedding': embedding_vector,
                            'source': 'weaviate'
                        })
                    return embeddings
                
            logger.info(f"No embeddings found in Weaviate for document {document_id}, falling back to SQLite")
        except Exception as e:
            logger.error(f"Error retrieving from Weaviate, falling back to SQLite: {str(e)}")
    
    # Fallback to SQLite
    session = Session()
    try:
        logger.info(f"Fetching embeddings for document {document_id} from SQLite")
        embeddings_db = session.query(Embedding).filter_by(document_id=document_id).all()
        
        # Convert SQLAlchemy objects to dictionaries
        embeddings = []
        for emb in embeddings_db:
            embedding_array = np.frombuffer(emb.embedding, dtype=np.float32)
            
            # Make sure the array has the right shape for the model
            if len(embedding_array) != model.get_sentence_embedding_dimension():
                embedding_array = embedding_array.reshape(-1, model.get_sentence_embedding_dimension())[0]
                
            embeddings.append({
                'id': emb.id,
                'document_id': emb.document_id,
                'text_chunk': emb.text_chunk,
                'embedding': embedding_array,
                'metadata': emb.embedding_metadata,
                'source': 'sqlite'
            })
            
        return embeddings
    except Exception as e:
        logger.error(f"Error retrieving embeddings from SQLite: {str(e)}", exc_info=True)
        raise e
    finally:
        session.close()

@app.route('/embeddings/<document_id>', methods=['GET'])
def get_embeddings_by_document(document_id):
    """Get all embeddings for a document"""
    try:
        logger.info(f"Retrieving embeddings for document: {document_id}")
        embeddings = get_embedding(document_id)
        
        if not embeddings or len(embeddings) == 0:
            return jsonify({"error": "No embeddings found for this document ID"}), 404
            
        # Convert embeddings to serializable format
        serializable_embeddings = []
        for emb in embeddings:
            serializable_emb = {
                'id': emb['id'],
                'document_id': emb['document_id'],
                'text_chunk': emb['text_chunk'],
                'source': emb.get('source', 'unknown')
            }
            
            # Don't return the actual embedding unless requested
            if request.args.get('include_vectors', 'false').lower() == 'true':
                if isinstance(emb['embedding'], np.ndarray):
                    serializable_emb['embedding'] = emb['embedding'].tolist()
                else:
                    serializable_emb['embedding'] = emb['embedding']
                    
            if 'metadata' in emb and emb['metadata']:
                serializable_emb['metadata'] = emb['metadata']
                
            serializable_embeddings.append(serializable_emb)
            
        return jsonify({
            'document_id': document_id,
            'count': len(serializable_embeddings),
            'embeddings': serializable_embeddings
        })
        
    except Exception as e:
        logger.error(f"Error retrieving embeddings: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/embed', methods=['POST'])
def create_embedding():
    """Create embeddings for a document or text."""
    try:
        data = request.json
        if not data:
            logger.error("No JSON data in request")
            return jsonify({"error": "No data provided"}), 400
        
        logger.info(f"Received embedding request with keys: {list(data.keys())}")
        
        # If text is directly provided, generate embedding for it
        if 'text' in data:
            text = data['text']
            logger.info(f"Generating embedding for provided text (length: {len(text)})")
            
            # Generate embedding
            embedding = model.encode(text)
            
            return jsonify({
                "embedding": embedding.tolist()
            })
        
        # For document processing
        document_id = data.get('document_id')
        metadata = data.get('metadata', {})
        
        if not document_id:
            logger.error("Missing document_id in request")
            return jsonify({"error": "Missing document_id"}), 400
        
        logger.info(f"Creating embeddings for document {document_id}")
        
        # Process either provided text or text chunks
        if 'text' in data:
            text = data['text']
            # Split text into chunks
            chunks = split_text(text)
            logger.info(f"Split text into {len(chunks)} chunks")
        elif 'text_chunks' in data:
            chunks = data['text_chunks']
            logger.info(f"Using {len(chunks)} provided text chunks")
        else:
            logger.error("Request must include either 'text' or 'text_chunks'")
            return jsonify({"error": "Missing text or text_chunks"}), 400
        
        # Create embeddings for each chunk
        results = []
        for i, chunk in enumerate(chunks):
            # Generate embedding
            try:
                embedding = model.encode(chunk)
                
                # Save to database
                result = save_embedding(
                    document_id=document_id,
                    text_chunk=chunk,
                    embedding_array=embedding,
                    metadata={
                        **metadata,
                        'chunk_index': i
                    }
                )
                
                results.append(result)
            except Exception as chunk_error:
                logger.error(f"Error processing chunk {i}: {str(chunk_error)}")
                # Continue with other chunks instead of failing completely
        
        logger.info(f"Successfully created {len(results)} embeddings for document {document_id}")
        
        return jsonify({
            "success": True,
            "message": f"Created {len(results)} embeddings",
            "embeddings": results
        })
        
    except Exception as e:
        logger.error(f"Error in create_embedding: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify the service is working properly"""
    status = {
        "status": "healthy",
        "database": "connected",
        "model": "loaded",
        "weaviate": "connected" if weav else "disabled"
    }
    
    # Check database connection
    try:
        session = Session()
        session.execute("SELECT 1")
        session.close()
    except Exception as e:
        status["database"] = "error"
        status["status"] = "unhealthy"
        logger.error(f"Database health check failed: {str(e)}")
    
    # Check model
    try:
        test_embedding = model.encode("test")
        if not isinstance(test_embedding, np.ndarray):
            status["model"] = "error"
            status["status"] = "unhealthy"
    except Exception as e:
        status["model"] = "error"
        status["status"] = "unhealthy"
        logger.error(f"Model health check failed: {str(e)}")
    
    # Check Weaviate if available
    if weav:
        try:
            weav.schema.get()
        except Exception as e:
            status["weaviate"] = "error"
            status["status"] = "unhealthy"
            logger.error(f"Weaviate health check failed: {str(e)}")
    
    return jsonify(status), 200 if status["status"] == "healthy" else 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
