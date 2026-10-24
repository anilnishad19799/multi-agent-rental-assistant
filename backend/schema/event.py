"""Pydantic schemas for SSE events."""
from pydantic import BaseModel
from typing import Optional


class SSEEvent(BaseModel):
    type: str
    data: dict
    agent: Optional[str] = None
    timestamp: Optional[str] = None


class AgentSwitchEvent(BaseModel):
    from_agent: str
    to_agent: str
    reason: str


class DataExtractedEvent(BaseModel):
    agent: str
    extracted_fields: dict
    confidence: float = 1.0
