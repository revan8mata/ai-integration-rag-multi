from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from database import base
from pgvector.sqlalchemy import Vector


class User(base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())


class Conversation(base):
    __tablename__ = 'conversations'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id',ondelete='CASCADE'))
    title = Column(String)
    created_at = Column(DateTime, default=func.now())

class Message(base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)

    conversation_id = Column(Integer, ForeignKey('conversations.id',ondelete='CASCADE'),nullable=False)
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=func.now())
    provider = Column(String,nullable=True)

class Document(base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id',ondelete='CASCADE'))
    filename = Column(String)
    content_hash = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=func.now())

class Chunk(base):
    __tablename__ = 'chunks'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id',ondelete='CASCADE'))
    text = Column(Text)
    embedding = Column(Vector(768))


class Webhooks(base):
    __tablename__ = 'webhooks'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id',ondelete='CASCADE'))
    url = Column(String)
    event_type = Column(String)
    created_at = Column(DateTime, default=func.now())










