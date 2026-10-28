"""Tests for Stopping/Cancelling Response Generation in Chat."""
import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.models.base import init_db
from backend.api.routes import _active_chat_tasks
from backend.observability.tracing import TraceCollector, get_trace_by_id

client = TestClient(app)


@pytest.mark.asyncio
async def test_stop_generation_endpoint_missing_session_id():
    """Verify POST /api/chat/stop rejects requests without session_id."""
    await init_db()
    res = client.post("/api/chat/stop", json={})
    assert res.status_code == 400
    assert "session_id is required" in res.json()["detail"]


@pytest.mark.asyncio
async def test_stop_generation_endpoint_no_active_task():
    """Verify POST /api/chat/stop gracefully handles when no task is running."""
    await init_db()
    dummy_session = f"session-no-task-{uuid4().hex[:6]}"
    res = client.post("/api/chat/stop", json={"session_id": dummy_session})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["session_id"] == dummy_session
    assert data["stopped"] is False


@pytest.mark.asyncio
async def test_stop_generation_cancels_active_task():
    """Verify POST /api/chat/stop cancels a registered active task."""
    await init_db()
    session_id = f"session-active-{uuid4().hex[:6]}"

    async def long_running_mock():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise

    loop = asyncio.get_event_loop()
    task = loop.create_task(long_running_mock())
    _active_chat_tasks[session_id] = task

    try:
        assert not task.done()
        res = client.post("/api/chat/stop", json={"session_id": session_id})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["session_id"] == session_id
        assert data["stopped"] is True

        # Let the loop propagate cancellation
        await asyncio.sleep(0.01)
        assert task.cancelled() or task.done()
        assert session_id not in _active_chat_tasks
    finally:
        if not task.done():
            task.cancel()


@pytest.mark.asyncio
async def test_orchestrator_handles_cancellation():
    """Verify orchestrator run() marks trace as STOPPED upon asyncio.CancelledError."""
    await init_db()
    session_id = f"test-cancel-{uuid4().hex[:6]}"

    trace = TraceCollector(
        session_id=session_id,
        user_id="test-user-cancel",
        user_email="cancel_test@example.com",
        endpoint="/api/chat",
        user_input="Long search prompt",
    )

    from backend.core.orchestrator import run
    from backend.agents import AgentFactory

    # Mock AgentFactory.create_agent to raise asyncio.CancelledError simulating user stopping mid-run
    async def mock_supervisor_process(*args, **kwargs):
        raise asyncio.CancelledError("Stopped by user")

    mock_agent = AsyncMock()
    mock_agent.process = mock_supervisor_process

    with patch.object(AgentFactory, "create_agent", return_value=mock_agent):
        await run(
            session_id=session_id,
            user_input="Find a flat in Koramangala",
            provider="groq",
            user_id="test-user-cancel",
            trace=trace,
        )

    # Check that trace recorded STOPPED status
    assert trace.status == "STOPPED"
    assert "stopped" in (trace.agent_response or "").lower()

    # Verify persisted trace in database
    db_trace = await get_trace_by_id(trace.trace_id)
    assert db_trace is not None
    assert db_trace["status"] == "STOPPED"


@pytest.mark.asyncio
async def test_subsequent_query_not_affected_after_stopping():
    """Verify that stopping Query 1 leaves a clean pubsub channel for Query 2."""
    await init_db()
    from backend.infra.pubsub.factory import get_pubsub
    from backend.events.publisher import publish_event
    from backend.events.types import EventType

    session_id = f"test-seq-{uuid4().hex[:6]}"
    pubsub = get_pubsub()

    # Step 1: Simulate Query 1 being stopped
    await publish_event(session_id, EventType.AGENT_START, {"agent": "supervisor"})
    await publish_event(session_id, EventType.DONE, {"stopped": True})

    # Call stop endpoint (which clears the pubsub channel)
    res_stop = client.post("/api/chat/stop", json={"session_id": session_id})
    assert res_stop.status_code == 200

    # Verify pubsub queue is clean
    q = pubsub.subscribe(session_id)
    assert q.empty()

    # Step 2: Simulate Query 2 starting in the same session
    await publish_event(session_id, EventType.AGENT_START, {"agent": "supervisor"})
    await publish_event(session_id, EventType.LLM_TOKEN, {"token": "Hello!"})
    await publish_event(session_id, EventType.DONE, {})

    # Read events for Query 2
    ev1 = await q.get()
    assert ev1["type"] == EventType.AGENT_START
    ev2 = await q.get()
    assert ev2["type"] == EventType.LLM_TOKEN
    assert ev2["data"]["token"] == "Hello!"
    ev3 = await q.get()
    assert ev3["type"] == EventType.DONE
    # Verify Query 2 is NOT marked stopped!
    assert ev3["data"].get("stopped") is not True


@pytest.mark.asyncio
async def test_groq_fallback_on_rate_limit():
    """Verify GroqClient falls back to secondary model when primary hits RateLimitError."""
    from pydantic import BaseModel
    from backend.services.llm.groq_client import GroqClient

    class SimpleSchema(BaseModel):
        answer: str

    groq_client = GroqClient()
    groq_client.candidate_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    # Mock parse method: fail for gpt-oss-120b, succeed for gpt-oss-20b
    calls = []

    async def mock_parse(*args, **kwargs):
        model = kwargs.get("model")
        calls.append(model)
        if "120b" in model:
            raise Exception("Rate limit reached for model openai/gpt-oss-120b (TPD limit 200000)")
        mock_res = AsyncMock()
        mock_res.choices = [AsyncMock(message=AsyncMock(parsed=SimpleSchema(answer="fallback_success")))]
        return mock_res

    with patch.object(groq_client.client.beta.chat.completions, "parse", side_effect=mock_parse):
        result = await groq_client.structured_output([{"role": "user", "content": "hi"}], SimpleSchema)
        assert result.answer == "fallback_success"
        # Verify it attempted primary and then fell back
        assert any("120b" in m for m in calls)
        assert any("20b" in m for m in calls or "qwen" in m for m in calls)

