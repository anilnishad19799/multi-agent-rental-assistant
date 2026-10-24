"""Session service — manages active user sessions."""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SessionService:
    """Manages user sessions and conversation state."""

    _active_sessions: Dict[str, dict] = {}

    @classmethod
    async def create_session(cls, session_id: str) -> dict:
        session = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "current_agent": "supervisor",
            "is_active": True,
        }
        cls._active_sessions[session_id] = session
        logger.info(f"Created session: {session_id}")
        return session

    @classmethod
    async def get_session(cls, session_id: str) -> Optional[dict]:
        return cls._active_sessions.get(session_id)

    @classmethod
    async def update_session(cls, session_id: str, data: dict) -> None:
        if session_id in cls._active_sessions:
            cls._active_sessions[session_id].update(data)

    @classmethod
    async def end_session(cls, session_id: str) -> None:
        if session_id in cls._active_sessions:
            cls._active_sessions[session_id]["is_active"] = False
            logger.info(f"Ended session: {session_id}")

    @classmethod
    async def is_active(cls, session_id: str) -> bool:
        session = cls._active_sessions.get(session_id)
        return session.get("is_active", False) if session else False
