"""SQLAlchemy models for conversations, messages, and memory."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    session_id = Column(String, unique=True, nullable=False)
    current_agent = Column(String, default="supervisor")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", lazy="selectin",
                            order_by="Message.created_at")
    memory_entries = relationship("ConversationMemory", back_populates="conversation", lazy="selectin")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_new_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    sender_type = Column(String, nullable=False)  # USER / AGENT
    agent_type = Column(String, nullable=True)  # rent / user_info / calendar / general / supervisor
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class ConversationMemory(Base):
    __tablename__ = "conversation_memory"

    id = Column(String, primary_key=True, default=_new_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    conversation = relationship("Conversation", back_populates="memory_entries")


class UserExtractedInfoLog(Base):
    __tablename__ = "user_extracted_info_log"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    field_name = Column(String, nullable=False)
    field_value = Column(Text, nullable=False)
    source_agent = Column(String, nullable=False)
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=_utcnow)
