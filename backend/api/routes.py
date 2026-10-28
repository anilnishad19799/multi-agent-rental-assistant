"""API routes — chat endpoint with session continuity support."""
import asyncio
import logging
from typing import Optional, Dict
from fastapi import APIRouter, Header, Depends, HTTPException, status
from uuid import uuid4

from backend.core.orchestrator import run
from backend.models.base import init_db
from backend.models import User
from backend.api.dependencies import get_current_user, require_current_user
from backend.repositories.user_repository import UserRepository
from backend.repositories.conversation_repository import ConversationRepository
import backend.models  # noqa: F401 — ensure all models registered

logger = logging.getLogger(__name__)
router = APIRouter()
user_repo = UserRepository()
conversation_repo = ConversationRepository()

_db_initialized = False
_active_chat_tasks: Dict[str, asyncio.Task] = {}


@router.post("/chat")
async def chat(
    payload: dict,
    authorization: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Accept a chat message. Requires user authentication.

    Request body:
        message: str — user message
        session_id: str (optional) — existing session for follow-up
        provider: str (optional) — LLM provider (openai/groq/gemini)
        user_id: str (optional) — authenticated user id

    Returns:
        session_id: str — use this to connect SSE stream
    """
    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True

    # Enforce authentication: user must be authenticated to access chat
    user_id = None
    if current_user:
        user_id = current_user.id
    elif payload.get("user_id"):
        user_obj = await user_repo.get_by_id(payload["user_id"])
        if user_obj:
            user_id = user_obj.id

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in or create an account to access the rental assistant.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate and isolate session specifically for this user
    req_session_id = payload.get("session_id") or str(uuid4())
    conv = await conversation_repo.get_or_create_conversation(req_session_id, user_id=user_id)
    session_id = conv.session_id

    # Resolve user email for observability
    user_email = current_user.email if current_user else None
    if not user_email and user_id:
        user_obj = await user_repo.get_by_id(user_id)
        if user_obj:
            user_email = user_obj.email

    # 1. Cancel any active task from a previous query in this session
    old_task = _active_chat_tasks.pop(session_id, None)
    if old_task and not old_task.done():
        old_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(old_task), timeout=0.1)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass

    # 2. Clear any stale events left in pubsub from prior cancelled/stopped queries
    from backend.infra.pubsub.factory import get_pubsub
    get_pubsub().clear(session_id)

    from backend.observability.tracing import TraceCollector
    trace = TraceCollector(
        session_id=session_id,
        user_id=user_id,
        user_email=user_email,
        endpoint="/api/chat",
        user_input=payload.get("message"),
        metadata={"provider": payload.get("provider", "groq")},
    )

    task = asyncio.create_task(
        run(
            session_id,
            payload["message"],
            provider=payload.get("provider"),
            user_id=user_id,
            trace=trace,
        )
    )
    _active_chat_tasks[session_id] = task

    def _task_done_cb(t):
        if _active_chat_tasks.get(session_id) is t:
            _active_chat_tasks.pop(session_id, None)

    task.add_done_callback(_task_done_cb)

    return {"session_id": session_id}


@router.post("/chat/stop")
async def stop_chat_generation(
    payload: dict,
    current_user: Optional[User] = Depends(get_current_user),
):
    """Stop/cancel active response generation for a given session."""
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id is required to stop generation",
        )

    task = _active_chat_tasks.pop(session_id, None)
    stopped = False
    if task and not task.done():
        task.cancel()
        stopped = True
        logger.info(f"[{session_id}] Chat generation task cancelled by user request")

    # Clear pubsub channel so no leftover events linger for subsequent queries
    from backend.infra.pubsub.factory import get_pubsub
    get_pubsub().clear(session_id)

    return {"status": "success", "session_id": session_id, "stopped": stopped}


@router.get("/chat/history")
async def get_chat_history(current_user: User = Depends(require_current_user)):
    """Fetch conversation history strictly for the authenticated user."""
    data = await conversation_repo.get_user_conversation_messages(current_user.id)
    return data


@router.post("/chat/new")
async def create_new_chat(current_user: User = Depends(require_current_user)):
    """Start a fresh, isolated conversation session for the authenticated user."""
    new_session_id = str(uuid4())
    conv = await conversation_repo.get_or_create_conversation(new_session_id, user_id=current_user.id)
    return {"session_id": conv.session_id}


@router.get("/agents")
async def list_agents():
    """List all registered agents."""
    from backend.agents import AgentFactory
    return {"agents": AgentFactory.list_agents()}