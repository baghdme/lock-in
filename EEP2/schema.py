from datetime import datetime
from typing import Dict, List
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Float, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import numpy as np

Base = declarative_base()

class User(Base):
    """Schema for users"""
    __tablename__ = 'users'

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    preferences = Column(JSON, default={})

    # Relationships
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    qa_pairs = relationship("QuestionAnswer", back_populates="user", cascade="all, delete-orphan")

class Document(Base):
    """Schema for stored documents"""
    __tablename__ = 'documents'

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    file_type = Column(String, nullable=False)
    document_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="documents")
    embeddings = relationship("Embedding", back_populates="document", cascade="all, delete-orphan")
    qa_pairs = relationship("QuestionAnswer", back_populates="document", cascade="all, delete-orphan")

class Embedding(Base):
    """Schema for document embeddings"""
    __tablename__ = 'embeddings'

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey('documents.id'), nullable=False)
    chunk_id = Column(String, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False)  # Store as JSON array
    created_at = Column(DateTime, default=func.now())

    # Relationships
    document = relationship("Document", back_populates="embeddings")

    def __init__(self, **kwargs):
        # Ensure embedding is stored as a list
        if 'embedding' in kwargs and isinstance(kwargs['embedding'], (list, np.ndarray)):
            kwargs['embedding'] = list(kwargs['embedding'])  # Convert numpy array to list if needed
        super().__init__(**kwargs)

class QuestionAnswer(Base):
    """Schema for stored question-answer pairs"""
    __tablename__ = 'qa_pairs'

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    document_id = Column(String, ForeignKey('documents.id'), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    context_used = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="qa_pairs")
    document = relationship("Document", back_populates="qa_pairs")

# MongoDB collection names
COLLECTIONS = {
    "users": "users",
    "documents": "documents",
    "embeddings": "embeddings",
    "qa_pairs": "qa_pairs"
}

# MongoDB indexes
INDEXES = {
    "users": [
        [("id", 1)],
        [("username", 1)],
        [("email", 1)]
    ],
    "documents": [
        [("id", 1)],
        [("user_id", 1)],
        [("created_at", -1)]
    ],
    "embeddings": [
        [("id", 1)],
        [("document_id", 1)],
        [("chunk_id", 1)]
    ],
    "qa_pairs": [
        [("id", 1)],
        [("user_id", 1)],
        [("document_id", 1)],
        [("created_at", -1)]
    ]
} 