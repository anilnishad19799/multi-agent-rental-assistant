"""SQLAlchemy model for production observability and system traces."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Text
from backend.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class TraceRecord(Base):
    """Stores full execution traces: API call, user, agent handoffs, prompts, outputs, and latencies."""
    __tablename__ = "traces"

    id = Column(String, primary_key=True, default=_new_uuid)
    trace_id = Column(String, index=True, nullable=False, unique=True)
    session_id = Column(String, index=True, nullable=True)
    user_id = Column(String, index=True, nullable=True)
    user_email = Column(String, nullable=True)
    endpoint = Column(String, nullable=False, default="/api/chat")
    status = Column(String, default="SUCCESS")  # SUCCESS, ERROR
    duration_ms = Column(Float, default=0.0)
    agents_invoked = Column(String, nullable=True)  # e.g. "supervisor,rent"
    user_input = Column(Text, nullable=True)
    agent_response = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    spans = Column(Text, nullable=True)  # JSON-encoded array of detailed span dicts
    metadata_json = Column(Text, nullable=True)  # Provider, model, langsmith run id, etc.
    created_at = Column(DateTime, default=_utcnow)
