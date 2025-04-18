import os
from dotenv import load_dotenv
import logging
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from schema import Base, User, Document, Embedding, QuestionAnswer
import uuid
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """Initialize database connection."""
        db_path = os.path.join(os.path.dirname(__file__), 'eep2.db')
        self.engine = create_engine(f'sqlite:///{db_path}', echo=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.logger = logging.getLogger(__name__)
        
        # Redis connection (optional, can be removed if not needed)
        try:
            self.redis_client = redis.from_url(
                os.getenv('REDIS_URI', 'redis://localhost:6379/0'),
                decode_responses=True
            )
            logger.info("Successfully connected to Redis")
        except:
            logger.warning("Redis connection failed, continuing without Redis")
            self.redis_client = None
        
        logger.info("Successfully connected to SQLite database")
    
    def get_session(self):
        """Get a new database session."""
        return self.Session()
    
    def get_redis(self):
        """Get Redis client"""
        return self.redis_client
    
    def _create_user_dict(self, user):
        """Helper function to create a user dictionary object from SQLAlchemy model"""
        if not user:
            return None
            
        # Create a dictionary with the user data
        user_dict = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "password_hash": getattr(user, "password_hash", None),
            "created_at": user.created_at
        }
        
        # Return a dictionary-like object instead of the SQLAlchemy model
        class UserDict:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
        return UserDict(**user_dict)
    
    # User methods
    def create_user(self, username: str, email: str, password_hash: str, preferences: dict = None):
        """Create a new user"""
        user_id = str(uuid.uuid4())
        self.logger.info(f"Creating user with ID: {user_id}, username: {username}")
        session = self.get_session()
        try:
            user = User(
                id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                preferences=preferences or {}
            )
            session.add(user)
            session.commit()
            
            # Expire the object to ensure it's not accidentally used after session is closed
            session.expunge(user)
            self.logger.info(f"User created successfully: {user_id}")
            
            return self._create_user_dict(user)
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating user: {str(e)}", exc_info=True)
            raise e
        finally:
            session.close()
    
    def get_user(self, user_id: str):
        """Get user by ID"""
        self.logger.info(f"Looking up user by ID: {user_id}")
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                self.logger.info(f"User ID not found: {user_id}")
                return None
            
            return self._create_user_dict(user)
        except Exception as e:
            self.logger.error(f"Error getting user by ID: {str(e)}", exc_info=True)
            raise e
        finally:
            session.close()
    
    def get_user_by_username(self, username: str):
        """Get user by username"""
        self.logger.info(f"Looking up user by username: {username}")
        session = self.get_session()
        try:
            user = session.query(User).filter(User.username == username).first()
            
            if not user:
                self.logger.info(f"User not found: {username}")
                return None
            
            return self._create_user_dict(user)
        except Exception as e:
            self.logger.error(f"Error looking up user: {str(e)}", exc_info=True)
            raise e
        finally:
            session.close()
    
    # Document methods
    def create_document(self, id: str, user_id: str, title: str, content: str, file_type: str, metadata: dict = None):
        """Create a new document"""
        session = self.get_session()
        try:
            doc = Document(
                id=id,  # Use the provided ID
                user_id=user_id,
                title=title,
                content=content,
                file_type=file_type,
                metadata=metadata or {}
            )
            session.add(doc)
            session.commit()
            return doc
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_document(self, document_id: str):
        """Get document by ID"""
        self.logger.info(f"Fetching document: {document_id}")
        session = self.get_session()
        try:
            document = session.query(Document).filter(Document.id == document_id).first()
            if document:
                self.logger.info(f"Found document: {document.id}, title: {document.title}")
            else:
                self.logger.warning(f"Document not found: {document_id}")
            return document
        except Exception as e:
            self.logger.error(f"Error fetching document: {str(e)}", exc_info=True)
            raise
        finally:
            session.close()
    
    def get_user_documents(self, user_id: str):
        """Get all documents for a user"""
        session = self.get_session()
        try:
            return session.query(Document).filter(Document.user_id == user_id).all()
        finally:
            session.close()
    
    # Embedding methods
    def create_embedding(self,id:str, document_id: str, chunk_id: str, chunk_text: str, embedding: list):
        """Create a new embedding"""
        self.logger.info(f"Creating embedding for document {document_id}, chunk {chunk_id}")
        session = self.get_session()
        try:
            # Verify document exists
            document = session.query(Document).filter(Document.id == document_id).first()
            if not document:
                self.logger.error(f"Cannot create embedding: Document {document_id} not found")
                raise ValueError(f"Document {document_id} not found")

            emb = Embedding(
                id=str(uuid.uuid4()),
                document_id=document_id,
                chunk_id=chunk_id,
                chunk_text=chunk_text,
                embedding=embedding
            )
            session.add(emb)
            session.commit()
            self.logger.info(f"Successfully created embedding {emb.id}")
            return emb
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error creating embedding: {str(e)}", exc_info=True)
            raise
        finally:
            session.close()
    
    def get_document_embeddings(self, document_id: str):
        """Get all embeddings for a document"""
        self.logger.info(f"Fetching embeddings for document: {document_id}")
        session = self.get_session()
        try:
            embeddings = session.query(Embedding).filter(Embedding.document_id == document_id).all()
            self.logger.info(f"Found {len(embeddings)} embeddings for document {document_id}")
            return embeddings
        except Exception as e:
            self.logger.error(f"Error fetching embeddings: {str(e)}", exc_info=True)
            raise
        finally:
            session.close()
    
    # Question-Answer methods
    def create_qa_pair(self, user_id: str, document_id: str, question: str, answer: str, context_used: str):
        """Create a new QA pair"""
        session = self.get_session()
        try:
            qa = QuestionAnswer(
                id=str(uuid.uuid4()),
                user_id=user_id,
                document_id=document_id,
                question=question,
                answer=answer,
                context_used=context_used
            )
            session.add(qa)
            session.commit()
            return qa
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_user_qa_history(self, user_id: str, limit: int = 10):
        """Get recent QA history for a user"""
        session = self.get_session()
        try:
            return session.query(QuestionAnswer)\
                .filter(QuestionAnswer.user_id == user_id)\
                .order_by(QuestionAnswer.created_at.desc())\
                .limit(limit)\
                .all()
        finally:
            session.close()
    
    def get_document_qa_history(self, document_id: str, limit: int = 10):
        """Get recent QA history for a document"""
        session = self.get_session()
        try:
            return session.query(QuestionAnswer)\
                .filter(QuestionAnswer.document_id == document_id)\
                .order_by(QuestionAnswer.created_at.desc())\
                .limit(limit)\
                .all()
        finally:
            session.close()
    
    # Cache methods
    def cache_qa_result(self, user_id: str, document_id: str, question: str, answer: str, ttl: int = 3600):
        """Cache a QA result in Redis"""
        cache_key = f"qa:{user_id}:{document_id}:{question}"
        self.redis_client.setex(cache_key, ttl, answer)
    
    def get_cached_qa_result(self, user_id: str, document_id: str, question: str):
        """Get a cached QA result from Redis"""
        cache_key = f"qa:{user_id}:{document_id}:{question}"
        return self.redis_client.get(cache_key)
    
    # Health check
    def health_check(self):
        """Check database health"""
        try:
            session = self.get_session()
            session.execute('SELECT 1')
            session.close()
            return {'status': 'healthy', 'database': 'connected'}
        except Exception as e:
            self.logger.error(f"Database health check failed: {str(e)}", exc_info=True)
            return {'status': 'unhealthy', 'error': str(e)}

# Create global database instance
db = Database() 