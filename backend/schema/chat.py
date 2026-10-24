"""Pydantic schemas for chat API request/response."""
from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    provider: Optional[str] = None  # openai, groq, gemini


class ChatResponse(BaseModel):
    session_id: str
    status: str = "processing"


class MessageResponse(BaseModel):
    id: str
    sender_type: str
    agent_type: Optional[str] = None
    content: str
    timestamp: str


class ConversationHistoryResponse(BaseModel):
    session_id: str
    messages: List[MessageResponse]
