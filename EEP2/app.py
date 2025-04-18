from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
import os
import uuid
import platform
from functools import wraps
from typing import List

import requests
import weaviate
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    flash,
)
from werkzeug.utils import secure_filename
from weaviate.embedded import EmbeddedOptions
import numpy as np

from database import Database
from schema import User, Document, Embedding, QuestionAnswer  # noqa: F401 (imported for type hints)

# ───────────────  basic config  ───────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s  %(message)s",
)
logger = logging.getLogger("EEP2")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = os.environ.get("SECRET_KEY", "dev_key_for_development")
app.config.update(
    UPLOAD_FOLDER=UPLOAD_DIR,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB
    ALLOWED_EXTENSIONS={"txt", "pdf", "doc", "docx", "csv", "json", "pptx"},
)

# ───────────────  external service URLs  ───────────────
IEP_PARSE_URL = os.getenv("IEP_PARSE_URL", "http://localhost:5003")
IEP_EMBED_URL = os.getenv("IEP_EMBED_URL", "http://localhost:5001")
IEP_QA_URL = os.getenv("IEP_QA_URL", "http://localhost:5005")

# ───────────────  Embedded Weaviate  ───────────────
weav = None
# Check if we're running on Windows
if platform.system() == "Windows":
    logger.info("Windows detected - Weaviate embedded is not supported on Windows. Using SQLite only.")
else:
    try:
        weav = weaviate.Client(
            embedded_options=EmbeddedOptions(
                hostname="127.0.0.1",
                port=8080,
                additional_env_vars={"AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED": "true"},
            )
        )
        logger.info("Embedded Weaviate started on 127.0.0.1:8080 (anonymous access)")

        # schema bootstrap
        if not weav.schema.exists("DocumentChunk"):
            weav.schema.create_class(
                {
                    "class": "DocumentChunk",
                    "description": "Text chunk with vector",
                    "vectorizer": "none",
                    "properties": [
                        {"name": "document_id", "dataType": ["string"]},
                        {"name": "user_id", "dataType": ["string"]},
                        {"name": "text", "dataType": ["text"]},
                        {"name": "chunk_index", "dataType": ["int"]},
                        {"name": "timestamp", "dataType": ["date"]},
                    ],
                }
            )
        if not weav.schema.exists("QAPair"):
            weav.schema.create_class(
                {
                    "class": "QAPair",
                    "description": "Persisted QA pairs",
                    "vectorizer": "none",
                    "properties": [
                        {"name": "document_id", "dataType": ["string"]},
                        {"name": "user_id", "dataType": ["string"]},
                        {"name": "question", "dataType": ["text"]},
                        {"name": "answer", "dataType": ["text"]},
                        {"name": "timestamp", "dataType": ["date"]},
                    ],
                }
            )
    except Exception as exc:
        logger.error("Failed to start embedded Weaviate → fallback to DB only", exc_info=True)
        weav = None

# ───────────────  helpers  ───────────────
db = Database()


def login_required(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("index"))
        return func(*args, **kwargs)

    return _wrapper


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


def get_user_from_request() -> str | None:
    if "user_id" in session:
        return session["user_id"]
    if request.headers.get("X-User-ID"):
        return request.headers["X-User-ID"]
    try:
        return json.loads(request.cookies.get("session", "{}")).get("user_id")
    except Exception:
        return None


# ───────────────  routes  ───────────────
@app.route("/")
def index():
    try:
        # Get current user if logged in
        current_user = None
        if "user_id" in session:
            user_id = session.get("user_id")
            current_user = db.get_user(user_id)
            if not current_user:
                # If user not found but session exists, clear it
                logger.warning(f"User ID in session not found in database: {user_id}")
                session.pop("user_id", None)
            
        return render_template("index.html", current_user=current_user)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}", exc_info=True)
        # In case of error, clear session
        session.pop("user_id", None)
        return render_template("index.html", current_user=None)


@app.route("/register", methods=["POST"])
def register():
    logger.info("Register route called")
    u, e, p = request.form.get("username"), request.form.get("email"), request.form.get("password")
    if not all([u, e, p]):
        flash("All fields are required")
        return redirect(url_for("index"))

    if db.get_user_by_username(u):
        flash("Username already exists")
        return redirect(url_for("index"))

    try:
        # Generate a user ID first
        user_id = str(uuid.uuid4())
        logger.info(f"Creating new user with ID: {user_id}")
        
        # Create the user with the pre-generated ID
        user = db.create_user(
            username=u, 
            email=e, 
            password_hash=hashlib.sha256(p.encode()).hexdigest()
        )
        
        # Store just the ID in the session (avoid using potentially detached object)
        session["user_id"] = user.id
        logger.info(f"User created successfully, ID stored in session: {session['user_id']}")
        flash("Account created!")
        return redirect(url_for("index"))
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}", exc_info=True)
        flash(f"Error creating account: {str(e)}")
        return redirect(url_for("index"))


@app.route("/login", methods=["POST"])
def login():
    logger.info("Login route called")
    u, p = request.form.get("username"), request.form.get("password")
    if not all([u, p]):
        flash("Username and password required")
        return redirect(url_for("index"))
    
    try:
        user = db.get_user_by_username(u)
        if not user or user.password_hash != hashlib.sha256(p.encode()).hexdigest():
            logger.warning(f"Invalid login attempt for username: {u}")
            flash("Invalid credentials")
            return redirect(url_for("index"))
        
        # Store just the ID in the session
        user_id = user.id
        session["user_id"] = user_id
        logger.info(f"User logged in successfully, ID stored in session: {user_id}")
        flash("Logged in")
        return redirect(url_for("index"))
    except Exception as e:
        logger.error(f"Error during login: {str(e)}", exc_info=True)
        flash(f"Login error: {str(e)}")
        return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    logger.info("Upload file route called")
    if "file" not in request.files:
        flash("No file part")
        return redirect(url_for("index"))

    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        flash("Invalid file")
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    logger.info(f"File saved to {path}")

    try:
        # ── parse ─────────────────────────
        logger.info(f"Sending file to parser service at {IEP_PARSE_URL}/parse")
        with open(path, "rb") as f:
            resp = requests.post(f"{IEP_PARSE_URL}/parse", files={"file": (filename, f)})
        resp.raise_for_status()
        parsed = resp.json()
        logger.info(f"File parsed successfully: {len(parsed.get('text', ''))} characters")

        # ── create doc metadata ───────────
        doc_id = str(uuid.uuid4())
        logger.info(f"Creating document with ID: {doc_id}")
        db.create_document(
            id=doc_id,
            user_id=session["user_id"],
            title=filename,
            content=parsed.get("text", ""),
            file_type=filename.rsplit(".", 1)[1].lower(),
            metadata={"original_filename": filename},
        )
        logger.info(f"Document created in database")

        # ── embed ─────────────────────────
        chunks: List[str] = [parsed["text"][i : i + 1000] for i in range(0, len(parsed["text"]), 1000)]
        logger.info(f"Split text into {len(chunks)} chunks")
        
        logger.info(f"Sending chunks to embedding service at {IEP_EMBED_URL}/embed")
        resp = requests.post(f"{IEP_EMBED_URL}/embed", json={"document_id": doc_id, "text_chunks": chunks}, timeout=60)
        resp.raise_for_status()
        
        embeddings_response = resp.json()
        logger.info(f"Embeddings response structure: {list(embeddings_response.keys())}")
        
        embeds = embeddings_response.get("embeddings", [])
        logger.info(f"Received {len(embeds)} embeddings from embedding service")
        
        if embeds and len(embeds) > 0:
            # Log the structure of the first embedding to help debug
            first_embed = embeds[0]
            logger.info(f"First embedding structure: {list(first_embed.keys())}")
            logger.info(f"First embedding metadata: {first_embed.get('metadata', {})}")
        else:
            logger.warning("No embeddings returned from service")
        
        # ── persist vectors ───────────────
        if weav:
            logger.info(f"Using Weaviate to store embeddings")
            with weav.batch as batch:
                batch.batch_size = 64
                for idx, emb in enumerate(embeds):
                    # We need to use the original embedding vectors from the response
                    # Note that the embedding service only returns IDs and text chunks, not vectors
                    embedding_vector = None
                    if "embedding" in emb:
                        embedding_vector = emb["embedding"]
                    
                    if embedding_vector:
                        batch.add_data_object(
                            data_object={
                                "document_id": doc_id,
                                "user_id": session["user_id"],
                                "text": emb["text_chunk"],
                                "chunk_index": idx,
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            class_name="DocumentChunk",
                            uuid=emb["id"],
                            vector=embedding_vector,
                        )
                    else:
                        logger.warning(f"Skipping embedding {emb['id']} - no vector data")
            flash("Document processed & embedded")
        else:
            logger.info(f"Using SQLite to store embeddings")
            for idx, emb in enumerate(embeds):
                try:
                    # We need to specifically request the embedding vectors from the embedding service
                    # Since they aren't included in the response by default
                    embedding_vector = None
                    
                    # Use the embedding API to get the vector for this text chunk
                    embed_resp = requests.post(
                        f"{IEP_EMBED_URL}/embed", 
                        json={"text": emb["text_chunk"]}, 
                        timeout=10
                    )
                    
                    if embed_resp.status_code == 200:
                        embedding_vector = embed_resp.json().get("embedding")
                    
                    if embedding_vector:
                        db.create_embedding(
                            id=emb["id"],
                            document_id=doc_id,
                            chunk_id=emb["id"],
                            chunk_text=emb["text_chunk"],
                            embedding=embedding_vector,
                        )
                    else:
                        logger.warning(f"Could not get embedding vector for chunk {idx}")
                except Exception as e:
                    logger.error(f"Error processing embedding {idx}: {str(e)}")
                    # Continue with other embeddings
            flash("Document processed (DB fallback)")

        print("ata3et")
        # Wait a moment to ensure all processing is complete
        import time
        time.sleep(1)
        print("woke up")
        # ── trigger initial QA processing ─────────
        try:
            print("trying")
            # Prepare a default initial question to get content summary
            initial_qa_data = {
                "user_id": session["user_id"],
                "document_id": doc_id,
                "question": "Please summarize the content of this document."
            }
            
            logger.info(f"Sending initial QA request to QA service for document: {doc_id}")
            qa_resp = requests.post(f"{IEP_QA_URL}/qa", json=initial_qa_data, timeout=60)
            print("the response u're waiting for is here", qa_resp)
            if qa_resp.status_code == 200:
                qa_result = qa_resp.json()
                logger.info(f"Initial QA processing successful: {len(qa_result.get('answer', ''))} characters in response")
                
                # Save the initial QA pair to database
                db.create_qa_pair(
                    user_id=session["user_id"],
                    document_id=doc_id,
                    question=initial_qa_data["question"],
                    answer=qa_result.get("answer", "No answer generated."),
                    context_used=json.dumps(qa_result.get("chunks", []))
                )
                logger.info("Initial QA pair saved to database")
                
                # Add success message
                flash("Document processed and initial summary generated!")
            else:
                logger.warning(f"Initial QA processing failed with status {qa_resp.status_code}: {qa_resp.text}")
                flash("Document processed, but summary generation failed. You can still ask questions.")
        except Exception as qa_error:
            logger.error(f"Error during initial QA processing: {str(qa_error)}", exc_info=True)
            flash("Document processed, but there was an error generating the summary.")
        
        logger.info(f"Processing complete, redirecting to QA test with document_id={doc_id}")
        return redirect(url_for("qa_test", document_id=doc_id))
    except Exception as exc:
        logger.error("Upload pipeline failed", exc_info=True)
        flash(f"Error processing document: {exc}")
        return redirect(url_for("index"))
    finally:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Temporary file removed: {path}")


@app.route("/qa-test")
@login_required
def qa_test():
    try:
        # Get the user_id from the session
        user_id = session.get("user_id")
        if not user_id:
            logger.error("No user_id in session")
            flash("Please log in to access this page")
            return redirect(url_for("index"))
            
        # Get the current user
        current_user = db.get_user(user_id)
        if not current_user:
            logger.error(f"User not found for ID: {user_id}")
            session.pop("user_id", None)  # Clear invalid session
            flash("User not found. Please log in again.")
            return redirect(url_for("index"))
            
        # Get documents for the user
        docs = db.get_user_documents(user_id)
        logger.info(f"Retrieved {len(docs)} documents for user {user_id}")
        
        # Pass current_user explicitly to the template
        return render_template(
            "qa_test.html", 
            documents=docs, 
            selected_document_id=request.args.get("document_id"),
            current_user=current_user
        )
    except Exception as e:
        logger.error(f"Error in qa_test route: {str(e)}", exc_info=True)
        flash(f"An error occurred: {str(e)}")
        return redirect(url_for("index"))


@app.route("/api/qa", methods=["POST"])
def api_qa():
    """Process a QA request and forward it to the QA service"""
    logger.info("API QA endpoint called")
    data = request.get_json()
    
    if not data:
        logger.error("Invalid request data: empty or not JSON")
        return jsonify({"error": "Invalid request data"}), 400
    
    # Log the request data for debugging
    logger.info(f"Request data: {data}")
    
    # Make sure required fields are present
    if 'document_id' not in data:
        logger.error("Missing document_id field")
        return jsonify({"error": "Missing document_id field"}), 400
    
    if 'question' not in data:
        logger.error("Missing question field")
        return jsonify({"error": "Missing question field"}), 400
    
    # Get user_id from data or session
    if 'user_id' not in data:
        # If no user_id in request, use session if available
        if 'user_id' in session:
            data['user_id'] = session['user_id']
        else:
            # Use a guest user_id if no user is logged in
            data['user_id'] = 'guest'
    
    logger.info(f"Using user ID for QA: {data['user_id']}")
    
    try:
        # Forward the request to the QA service
        logger.info(f"Forwarding request to QA service at {IEP_QA_URL}/qa")
        resp = requests.post(f"{IEP_QA_URL}/qa", json=data, timeout=30)
        
        # Log the response status
        logger.info(f"QA service response status: {resp.status_code}")
        
        if resp.status_code != 200:
            logger.error(f"QA service error: {resp.text}")
            return jsonify({"error": f"QA service returned error: {resp.text}"}), resp.status_code
            
        resp.raise_for_status()
        
        # Parse the response
        response_data = resp.json()
        logger.info(f"QA service response: {response_data}")
        
        # Only save to database if user is logged in (not guest)
        if 'answer' in response_data and data['user_id'] != 'guest':
            try:
                logger.info("Saving QA pair to database")
                db.create_qa_pair(
                    user_id=data['user_id'],
                    document_id=data['document_id'],
                    question=data['question'],
                    answer=response_data['answer'],
                    context_used=json.dumps(response_data.get('context', []))
                )
                logger.info("QA pair saved successfully")
            except Exception as db_error:
                # Log the error but don't fail the request
                logger.error(f"Error saving QA pair to database: {str(db_error)}", exc_info=True)
        
        # Return the response from the QA service
        return response_data
    except requests.RequestException as e:
        logger.error(f"Error communicating with QA service: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get answer: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in QA endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route("/api/qa/history", methods=["GET"])
def api_qa_history():
    """Get QA history for a user and document"""
    logger.info("QA history endpoint called")
    document_id = request.args.get("document_id")
    user_id = request.args.get("user_id") or session.get("user_id") or "guest"
    
    if not document_id:
        logger.error("Missing document_id parameter")
        return jsonify({"error": "Missing document_id parameter"}), 400
    
    logger.info(f"Getting QA history for document {document_id} and user {user_id}")
    
    # If user is guest, return empty history
    if user_id == "guest":
        logger.info("Guest user, returning empty history")
        return jsonify([])
    
    try:
        # Get QA history from the database
        qa_history = db.get_document_qa_history(document_id)
        
        # Format the history for the frontend
        formatted_history = [
            {
                "id": qa.id,
                "question": qa.question,
                "answer": qa.answer,
                "created_at": qa.created_at.isoformat() if qa.created_at else None
            }
            for qa in qa_history
        ]
        
        logger.info(f"Retrieved {len(formatted_history)} QA pairs")
        return jsonify(formatted_history)
    except Exception as e:
        logger.error(f"Error retrieving QA history: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get QA history: {str(e)}"}), 500


@app.route("/api/documents/<document_id>/embeddings", methods=["GET"])
def api_document_embeddings(document_id):
    """Get embeddings for a document"""
    try:
        # Determine user ID from session or header
        user_id = session.get("user_id") or request.headers.get("X-User-ID")
        if not user_id:
            logger.warning("No user ID found in session or headers")
            return jsonify({"error": "Authentication required"}), 401
            
        # Verify document exists and belongs to the user
        doc = db.get_document(document_id)
        if not doc:
            logger.error(f"Document not found: {document_id}")
            return jsonify({"error": "Document not found"}), 404
            
        if doc.user_id != user_id:
            logger.warning(f"Access denied to document {document_id} for user {user_id}")
            return jsonify({"error": "Access denied"}), 403
            
        # Get embeddings from the database
        embeddings = db.get_document_embeddings(document_id)
        logger.info(f"Retrieved {len(embeddings)} embeddings for document {document_id}")
        
        # Format the embeddings for the frontend
        formatted_embeddings = [
            {
                "id": emb.id,
                "document_id": emb.document_id,
                "chunk_id": emb.chunk_id,
                "chunk_text": emb.chunk_text,
                "embedding": emb.embedding
            }
            for emb in embeddings
        ]
        
        return jsonify(formatted_embeddings)
    except Exception as e:
        logger.error(f"Error retrieving embeddings: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get embeddings: {str(e)}"}), 500


@app.route("/api/documents/<document_id>", methods=["GET"])
def api_get_document(document_id):
    """Get a document by ID"""
    try:
        # Determine user ID from session or header
        user_id = session.get("user_id") or request.headers.get("X-User-ID")
        if not user_id:
            logger.warning("No user ID found in session or headers")
            return jsonify({"error": "Authentication required"}), 401
        
        logger.info(f"Getting document {document_id} for user {user_id}")
        
        # Get document from database
        doc = db.get_document(document_id)
        
        if not doc:
            logger.error(f"Document not found: {document_id}")
            return jsonify({"error": "Document not found"}), 404
            
        if doc.user_id != user_id:
            logger.warning(f"Access denied to document {document_id} for user {user_id}")
            return jsonify({"error": "Access denied"}), 403
            
        # Format the document for the frontend
        formatted_doc = {
            "id": doc.id,
            "title": doc.title,
            "file_type": doc.file_type,
            "metadata": doc.metadata,
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        }
        
        return jsonify(formatted_doc)
    except Exception as e:
        logger.error(f"Error retrieving document: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get document: {str(e)}"}), 500


@app.route("/health")
def health():
    status = {"status": "healthy"}
    try:
        status["iep_parse"] = requests.get(f"{IEP_PARSE_URL}/health", timeout=3).ok
        status["iep_embed"] = requests.get(f"{IEP_EMBED_URL}/health", timeout=3).ok
        status["iep_qa"] = requests.get(f"{IEP_QA_URL}/health", timeout=3).ok
    except Exception:
        pass

    if weav:
        try:
            weav.cluster.get_nodes_status()
            status["weaviate"] = True
        except Exception:
            status["weaviate"] = False
    else:
        status["weaviate"] = False

    if not all(status.values()):
        status["status"] = "unhealthy"
        return jsonify(status), 503
    return jsonify(status)


@app.route("/api/qa/store", methods=["POST"])
def api_store_qa():
    """Store a QA pair directly (called by the QA service)"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Invalid request data"}), 400
    
    # Check required fields
    required_fields = ['user_id', 'document_id', 'question', 'answer']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400
    
    try:
        # Save the QA pair
        qa = db.create_qa_pair(
            user_id=data['user_id'],
            document_id=data['document_id'],
            question=data['question'],
            answer=data['answer'],
            context_used=json.dumps(data.get('context', []))
        )
        
        return jsonify({
            "id": qa.id,
            "document id":qa.document_id,
            "status": "success",
            "message": "QA pair stored successfully"
        })
    except Exception as e:
        logger.error(f"Error storing QA pair: {str(e)}")
        return jsonify({"error": f"Failed to store QA pair: {str(e)}"}), 500


@app.route("/api/internal/documents/<document_id>", methods=["GET"])
def api_get_document_internal(document_id):
    """Get a document by ID - internal endpoint for QA service, no auth required"""
    try:
        logger.info(f"Internal API - Getting document {document_id}")
        
        # Get document from database
        doc = db.get_document(document_id)
        
        if not doc:
            logger.error(f"Document not found: {document_id}")
            return jsonify({"error": "Document not found"}), 404
            
        # Format the document for the frontend
        formatted_doc = {
            "id": doc.id,
            "title": doc.title,
            "file_type": doc.file_type,
            "metadata": doc.metadata,
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        }
        
        return jsonify(formatted_doc)
    except Exception as e:
        logger.error(f"Error retrieving document: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get document: {str(e)}"}), 500


@app.route("/api/internal/documents/<document_id>/embeddings", methods=["GET"])
def api_document_embeddings_internal(document_id):
    """Get embeddings for a document - internal endpoint for QA service, no auth required"""
    try:
        logger.info(f"Internal API - Getting embeddings for document {document_id}")
            
        # Get document from database
        doc = db.get_document(document_id)
        
        if not doc:
            logger.error(f"Document not found: {document_id}")
            return jsonify({"error": "Document not found"}), 404
            
        # Get embeddings from the database
        embeddings = db.get_document_embeddings(document_id)
        logger.info(f"Retrieved {len(embeddings)} embeddings for document {document_id}")
        
        # Check if we should include vectors
        include_vectors = request.args.get("include_vectors", "false").lower() == "true"
        
        # Format the embeddings for the frontend
        formatted_embeddings = []
        for emb in embeddings:
            embedding_data = {
                "id": emb.id,
                "document_id": emb.document_id,
                "chunk_id": emb.chunk_id,
                "text_chunk": emb.chunk_text,
            }
            
            if include_vectors:
                # Convert embedding to list for JSON serialization if it's requested
                if isinstance(emb.embedding, np.ndarray):
                    embedding_data["embedding"] = emb.embedding.tolist()
                elif isinstance(emb.embedding, list):
                    embedding_data["embedding"] = emb.embedding
                else:
                    # Try to convert from binary to array
                    try:
                        embedding_array = np.frombuffer(emb.embedding, dtype=np.float32)
                        embedding_data["embedding"] = embedding_array.tolist()
                    except Exception as e:
                        logger.error(f"Error converting embedding: {str(e)}")
            
            formatted_embeddings.append(embedding_data)
        
        return jsonify(formatted_embeddings)
    except Exception as e:
        logger.error(f"Error retrieving embeddings: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get embeddings: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
