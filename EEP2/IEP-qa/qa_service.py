from flask import Flask, request, jsonify
import os
import json
import logging
import platform
import requests
import numpy as np
import uuid
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import openai
import weaviate
from datetime import datetime
import faiss
from sklearn.metrics.pairwise import cosine_similarity
from flask_cors import CORS

# Import the database from parent directory
import sys
import os.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import Database

# Initialize database
db = Database()

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service URLs
EEP2_URL = os.environ.get('EEP2_URL', 'http://localhost:5000')
IEP_EMBED_URL = os.environ.get('IEP_EMBED_URL', 'http://localhost:5001')
WEAV_URL = os.environ.get('WEAV_URL', 'http://localhost:8080')
# No API key is needed for anonymous access
WEAV_STARTUP_TIMEOUT = int(os.environ.get('WEAV_STARTUP_TIMEOUT', '20'))  # Increased timeout

# Initialize Weaviate client with improved error handling
weav = None
# Check if we're running on Windows
if platform.system() == "Windows":
    logger.info("Windows detected - Weaviate is not supported on Windows. Using EEP2 API only.")
else:
    try:
        logger.info(f"Attempting to connect to Weaviate at {WEAV_URL}")
        
        # Connect with a longer timeout
        weav = weaviate.Client(
            url=WEAV_URL
        )
        logger.info(f"Connected to Weaviate at {WEAV_URL}")
    except Exception as e:
        logger.error(f"Failed to initialize Weaviate: {str(e)}", exc_info=True)
        weav = None

# Initialize the embedding model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
# Check if API key is set
has_openai_key = bool(openai.api_key)
if not has_openai_key:
    logger.warning("OpenAI API key not set. Will use fallback responses for testing.")

# Check if a response indicates a schedule modification
def is_schedule_modification(text):
    """Check if the answer indicates a schedule modification request."""
    # This is a simple check - in practice, you might use a more sophisticated approach
    keywords = ["schedule", "meeting", "appointment", "calendar", "reschedule"]
    text_lower = text.lower()
    
    # Check if any schedule-related keywords are present
    if any(keyword in text_lower for keyword in keywords):
        # Check for action verbs
        action_verbs = ["add", "create", "schedule", "set", "book", "change", "modify", "cancel", "delete", "remove"]
        if any(verb in text_lower for verb in action_verbs):
            return True
    
    return False

# Extract schedule modification details
def extract_schedule_details(text):
    """Extract schedule modification details from text."""
    # In a real implementation, you would use NLP to extract entities and intents
    # For this example, we'll use a simpler approach
    
    # Determine the type of modification
    action = "unknown"
    if any(word in text.lower() for word in ["add", "create", "schedule", "set", "book"]):
        action = "create"
    elif any(word in text.lower() for word in ["change", "modify", "update", "reschedule"]):
        action = "update"
    elif any(word in text.lower() for word in ["cancel", "delete", "remove"]):
        action = "delete"
    
    # Very basic extraction of date/time - would use proper entity extraction in production
    # For this demo, we'll just return a simplified structure
    return {
        "action": action,
        "text": text,
        # Additional fields would be extracted here in a real implementation
        # "date": extracted_date,
        # "time": extracted_time,
        # "title": extracted_title,
        # "participants": extracted_participants,
    }

@app.route('/qa', methods=['POST'])
def qa():
    """QA endpoint for answering questions about documents."""
    
    print("made it to the other side")
    try:
        data = request.json
        logger.info(f"Received QA request: {data}")
        
        # Validate input data
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Get required fields
        user_id = data.get('user_id', 'guest')
        document_id = data.get('document_id')
        question = data.get('question')
        
        if not document_id:
            return jsonify({"error": "Missing required field: document_id"}), 400
            
        if not question:
            return jsonify({"error": "Missing required field: question"}), 400
        
        # Get document from the database
        document = db.get_document(document_id)
        if not document:
            return jsonify({"error": f"Document not found: {document_id}"}), 404
        
        logger.info(f"Retrieved document: {document.title}")
        
        # Get embeddings from the database
        embeddings = db.get_document_embeddings(document_id)
        if not embeddings:
            return jsonify({"error": f"No embeddings found for document: {document_id}"}), 404
            
        logger.info(f"Retrieved {len(embeddings)} embeddings for document")
        
        # Generate embedding for the query
        try:
            embedding_response = requests.post(
                f"{IEP_EMBED_URL}/embed", 
                json={"text": question}
            )
            
            if embedding_response.status_code != 200:
                logger.error(f"Failed to generate query embedding: {embedding_response.status_code}")
                # Proceed without embeddings - use the full document text as context
                context = document.content[:5000]  # Limit to first 5000 chars
                logger.info("Using document content as context (no embedding)")
            else:
                # Process embeddings to find most relevant chunks
                query_embedding = np.array(embedding_response.json().get("embedding", []))
                
                # Create context from relevant chunks
                best_chunks = []
                for emb in embeddings:
                    try:
                        # Convert embedding from database format
                        if isinstance(emb.embedding, bytes):
                            chunk_embedding = np.frombuffer(emb.embedding, dtype=np.float32)
                        else:
                            chunk_embedding = np.array(emb.embedding)
                            
                        # Calculate similarity
                        similarity = cosine_similarity([query_embedding], [chunk_embedding])[0][0]
                        
                        best_chunks.append({
                            "chunk_id": emb.id,
                            "text": emb.chunk_text,
                            "similarity": float(similarity)
                        })
                    except Exception as e:
                        logger.error(f"Error processing embedding {emb.id}: {str(e)}")
                        continue
                
                # Sort by similarity and take top chunks
                best_chunks.sort(key=lambda x: x["similarity"], reverse=True)
                best_chunks = best_chunks[:5]
                
                # Create context from best chunks
                context = "\n".join([chunk["text"] for chunk in best_chunks])
        except Exception as e:
            logger.error(f"Error processing embeddings: {str(e)}")
            # Fallback to document text
            context = document.content[:5000]
            best_chunks = []
        
        # Generate answer using OpenAI
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return jsonify({"error": "OpenAI API key not set"}), 500
            
        completion = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer the question based only on the provided context. If the answer cannot be found in the context, say 'I don't have enough information to answer this question.'"}
            ]
        )
        
        answer = completion.choices[0].message.content
        
        # Store QA pair in database
        try:
            qa_pair = db.create_qa_pair(
                user_id=user_id,
                document_id=document_id,
                question=question,
                answer=answer,
                context_used=json.dumps(best_chunks)
            )
            logger.info(f"Saved QA pair with ID: {qa_pair.id}")
        except Exception as e:
            logger.error(f"Error saving QA pair: {str(e)}")
        
        # Return response
        return jsonify({
            "answer": answer,
            "chunks": best_chunks
        })
    except Exception as e:
        logger.error(f"Error in QA endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

def get_embeddings_from_eep2(user_id, document_id, query):
    """Retrieve embeddings from EEP2 and find relevant chunks."""
    try:
        # Verify document exists
        doc_data = verify_document_exists(document_id, user_id)
        if not doc_data:
            logger.error(f"Document not found: {document_id} for user {user_id}")
            return None, []
        
        # Get embeddings data
        embeddings_data = doc_data["embeddings"]
        
        # Generate embedding for the query
        embedding_response = requests.post(
            f"{IEP_EMBED_URL}/embed", 
            json={"text": query}
        )
        
        if embedding_response.status_code != 200:
            logger.error("Failed to generate query embedding")
            return None, []
            
        query_embedding = np.array(embedding_response.json()["embedding"])
        
        # Find most similar chunks using cosine similarity
        chunks_with_similarity = []
        for embedding_item in embeddings_data:
            chunk_embedding = np.array(embedding_item["embedding"])
            similarity = cosine_similarity([query_embedding], [chunk_embedding])[0][0]
            
            chunks_with_similarity.append({
                "text": embedding_item["text_chunk"],
                "similarity": float(similarity)
            })
        
        # Sort by similarity and take top 5
        chunks_with_similarity.sort(key=lambda x: x["similarity"], reverse=True)
        relevant_chunks = chunks_with_similarity[:5]
        
        # Extract just the text for context
        text_chunks = [chunk["text"] for chunk in relevant_chunks]
        context = "\n".join(text_chunks)
        
        logger.info(f"Generated context from {len(text_chunks)} relevant chunks")
        return context, text_chunks
        
    except Exception as e:
        logger.error(f"Error retrieving embeddings from EEP2: {str(e)}", exc_info=True)
        return None, []

def store_qa_pair_in_eep2(user_id, document_id, query, answer, context=""):
    """Store Q&A pair in EEP2 API."""
    try:
        # Prepare data for EEP2 API
        qa_data = {
            "user_id": user_id,
            "document_id": document_id,
            "question": query,  # Use 'question' key as expected by EEP2
            "answer": answer,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Storing QA pair in EEP2 for document {document_id}")
        
        # Store Q&A pair in EEP2
        response = requests.post(f"{EEP2_URL}/api/qa/store", json=qa_data)
        
        if response.status_code != 200 and response.status_code != 201:
            logger.error(f"Failed to store QA pair in EEP2: {response.text}")
            return False
            
        logger.info(f"Successfully stored QA pair in EEP2")
        return True
        
    except Exception as e:
        logger.error(f"Error storing QA pair in EEP2: {str(e)}", exc_info=True)
        return False

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        status = {
            'status': 'healthy',
            'services': {}
        }
        
        # Check EEP2 connection
        try:
            response = requests.get(f"{EEP2_URL}/health")
            response.raise_for_status()
            status['services']['eep2'] = 'connected'
        except Exception as e:
            logger.error(f"EEP2 health check failed: {str(e)}")
            status['services']['eep2'] = 'disconnected'
            status['status'] = 'degraded'  # Set to degraded since EEP2 is essential
        
        # Check IEP-embed connection
        try:
            response = requests.get(f"{IEP_EMBED_URL}/health")
            response.raise_for_status()
            status['services']['iep_embed'] = 'connected'
        except Exception as e:
            logger.error(f"IEP-embed health check failed: {str(e)}")
            status['services']['iep_embed'] = 'disconnected'
            status['status'] = 'degraded'  # Set to degraded since embedding is essential
        
        # Check Weaviate connection (optional)
        if weav:
            try:
                weav_status = weav.cluster.get_nodes_status()
                status['services']['weaviate'] = 'connected'
            except Exception as e:
                logger.error(f"Weaviate health check failed: {str(e)}")
                status['services']['weaviate'] = 'disconnected'
                # Don't set unhealthy because Weaviate is optional
        else:
            status['services']['weaviate'] = 'not_configured'
        
        # Test embedding model
        try:
            _ = embedding_model.encode(['test'])
            status['services']['embedding_model'] = 'loaded'
        except Exception as e:
            logger.error(f"Embedding model check failed: {str(e)}")
            status['services']['embedding_model'] = 'error'
            status['status'] = 'unhealthy'
        
        return jsonify(status), 200 if status['status'] == 'healthy' else 500
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

def verify_document_exists(document_id, user_id):
    """Verify document exists and fetch its embeddings from EEP2."""
    try:
        # Get document from EEP2 using internal API that doesn't require auth
        logger.info(f"Verifying document exists in EEP2: {document_id}")
        document_url = f"{EEP2_URL}/api/internal/documents/{document_id}"
        logger.info(f"Making request to: {document_url}")
        
        response = requests.get(document_url)
        
        if response.status_code != 200:
            logger.error(f"Document not found: {document_id}. Status: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
        document = response.json()
        logger.info(f"Document found: {document.get('title', document_id)}")
        
        # Get embeddings from EEP2 using internal API
        embeddings_url = f"{EEP2_URL}/api/internal/documents/{document_id}/embeddings"
        logger.info(f"Retrieving embeddings from: {embeddings_url}")
        
        emb_response = requests.get(embeddings_url, params={"include_vectors": "true"})
        
        if emb_response.status_code != 200:
            logger.error(f"Failed to retrieve embeddings. Status: {emb_response.status_code}")
            logger.error(f"Response: {emb_response.text}")
            return None
            
        embeddings_data = emb_response.json()
        
        # Log the structure of the embeddings response
        if isinstance(embeddings_data, dict):
            if 'embeddings' in embeddings_data:
                logger.info(f"Retrieved {len(embeddings_data['embeddings'])} embeddings")
                # Use the 'embeddings' field from the response
                embeddings_data = embeddings_data['embeddings']
            else:
                logger.info(f"Embeddings response has keys: {list(embeddings_data.keys())}")
        elif isinstance(embeddings_data, list):
            logger.info(f"Retrieved {len(embeddings_data)} embeddings as list")
        else:
            logger.error(f"Unexpected embeddings format: {type(embeddings_data)}")
            return None
        
        return {
            "document": document,
            "embeddings": embeddings_data
        }
        
    except Exception as e:
        logger.error(f"Error verifying document: {str(e)}", exc_info=True)
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005) 