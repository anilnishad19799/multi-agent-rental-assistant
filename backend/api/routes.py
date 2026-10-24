"""API routes — chat endpoint with session continuity support."""
from fastapi import APIRouter
from uuid import uuid4
import asyncio

from backend.core.orchestrator import run
from backend.models.base import init_db
import backend.models  # noqa: F401 — ensure all models registered

router = APIRouter()

_db_initialized = False


@router.post("/chat")
async def chat(payload: dict):
    """Accept a chat message. Supports new and existing sessions.

    Request body:
        message: str — user message
        session_id: str (optional) — existing session for follow-up
        provider: str (optional) — LLM provider (openai/groq/gemini)

    Returns:
        session_id: str — use this to connect SSE stream
    """
    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True

    # Support follow-up messages on same session
    session_id = payload.get("session_id") or str(uuid4())

    asyncio.create_task(
        run(session_id, payload["message"], provider=payload.get("provider"))
    )

    return {"session_id": session_id}


@router.get("/agents")
async def list_agents():
    """List all registered agents."""
    from backend.agents import AgentFactory
    return {"agents": AgentFactory.list_agents()}