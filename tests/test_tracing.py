"""Tests for Observability & Tracing (LangSmith & Local Trace System)."""
import asyncio
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.models.base import init_db
from backend.observability.tracing import (
    TraceCollector,
    TraceSpan,
    get_current_trace,
    get_recent_traces,
    get_trace_by_id,
    get_langsmith_info,
)
from backend.observability.logger import get_logger

client = TestClient(app)


@pytest.mark.asyncio
async def test_trace_collector_lifecycle():
    """Verify trace collector correctly accumulates spans, agents, and durations."""
    await init_db()

    with TraceCollector(
        session_id="test-session-123",
        user_id="user-456",
        user_email="testuser@example.com",
        endpoint="/api/chat",
        user_input="Looking for a 2-sharing PG in Bangalore",
    ) as trace:
        assert get_current_trace() is trace
        assert trace.user_email == "testuser@example.com"

        # Record agent invocation
        trace.record_agent_invocation("supervisor")
        trace.record_agent_invocation("rent")

        # Record supervisor routing span
        span1 = trace.start_span(
            name="Supervisor Routing",
            span_type="supervisor",
            inputs={"query": "Looking for a 2-sharing PG"},
        )
        await asyncio.sleep(0.01)
        span1.finish(outputs={"target_agent": "rent", "reasoning": "User looking for rental property"})

        # Record tool span
        span2 = trace.start_span(
            name="Property Database Search",
            span_type="tool",
            inputs={"city": "Bangalore", "sharing_type": "2-sharing"},
        )
        await asyncio.sleep(0.01)
        span2.finish(outputs={"matched_count": 3})

        trace.finish(
            agent_response="Found 3 matching properties in Bangalore.",
            status="SUCCESS",
        )

    # Let async DB write finish
    await asyncio.sleep(0.05)

    assert trace.duration_ms > 0
    assert trace.status == "SUCCESS"
    assert len(trace.spans) == 2
    assert trace.agents_invoked == ["supervisor", "rent"]

    # Verify query
    fetched = await get_trace_by_id(trace.trace_id)
    assert fetched is not None
    assert fetched["trace_id"] == trace.trace_id
    assert fetched["user_email"] == "testuser@example.com"
    assert fetched["agents_invoked"] == ["supervisor", "rent"]
    assert len(fetched["spans"]) == 2
    assert fetched["spans"][0]["name"] == "Supervisor Routing"
    assert fetched["spans"][1]["name"] == "Property Database Search"


@pytest.mark.asyncio
async def test_trace_filtering_by_user_and_agent():
    """Verify traces can be filtered by user_id and agent."""
    await init_db()

    with TraceCollector(
        session_id="session-user-a",
        user_id="user-a",
        user_email="userA@example.com",
        user_input="Query A",
    ) as trace_a:
        trace_a.record_agent_invocation("rent")
        trace_a.finish("Response A")

    with TraceCollector(
        session_id="session-user-b",
        user_id="user-b",
        user_email="userB@example.com",
        user_input="Query B",
    ) as trace_b:
        trace_b.record_agent_invocation("calendar")
        trace_b.finish("Response B")

    await asyncio.sleep(0.05)

    # Filter by user_a
    user_a_traces = await get_recent_traces(user_id="user-a")
    assert any(t["trace_id"] == trace_a.trace_id for t in user_a_traces)
    assert not any(t["trace_id"] == trace_b.trace_id for t in user_a_traces)

    # Filter by agent
    calendar_traces = await get_recent_traces(agent="calendar")
    assert any(t["trace_id"] == trace_b.trace_id for t in calendar_traces)


@pytest.mark.asyncio
async def test_trace_double_finish_no_integrity_error():
    """Verify that calling finish() explicitly and exiting context manager does not raise IntegrityError."""
    await init_db()

    with TraceCollector(
        session_id="double-finish-sess",
        user_email="vinod@gmail.com",
        user_input="yes",
    ) as trace:
        trace.record_agent_invocation("supervisor")
        trace.finish(agent_response="First explicit finish", status="SUCCESS")

    # Exiting the 'with' block invokes __exit__ (potential 2nd finish call)
    # Also test an explicit 3rd call to finish() directly
    trace.finish(agent_response="Second explicit finish", status="SUCCESS")

    await asyncio.sleep(0.05)

    fetched = await get_trace_by_id(trace.trace_id)
    assert fetched is not None
    assert fetched["trace_id"] == trace.trace_id
    assert fetched["status"] == "SUCCESS"
    assert fetched["user_email"] == "vinod@gmail.com"


@pytest.mark.asyncio
async def test_langsmith_config_info():
    """Verify LangSmith status payload returns structure properly."""
    info = get_langsmith_info()
    assert "langsmith_installed" in info
    assert "langsmith_active" in info
    assert "dashboard_url" in info
    assert "instructions" in info


def ensure_admin_sync():
    """Seed admin@gmail.com synchronously for test client execution."""
    import sqlite3
    import uuid
    from backend.services.auth_service import hash_password
    con = sqlite3.connect("rental_system.db")
    cur = con.cursor()
    cur.execute("SELECT id FROM users WHERE email='admin@gmail.com'")
    row = cur.fetchone()
    pw_hash = hash_password("Admin@1234")
    if not row:
        cur.execute(
            "INSERT INTO users (id, name, email, password_hash, is_admin) VALUES (?, ?, ?, ?, 1)",
            (str(uuid.uuid4()), "System Admin", "admin@gmail.com", pw_hash),
        )
    else:
        cur.execute(
            "UPDATE users SET password_hash=?, is_admin=1 WHERE email='admin@gmail.com'",
            (pw_hash,),
        )
    con.commit()
    con.close()


def get_admin_token() -> str:
    """Authenticate as admin@gmail.com and return access token."""
    ensure_admin_sync()
    res = client.post("/api/auth/login", json={
        "email": "admin@gmail.com",
        "password": "Admin@1234",
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json()["token"]


def test_admin_tracing_access_control():
    """Verify traces are restricted: 401 for unauthenticated, 403 for normal users, 200 for admin."""
    import uuid
    # 1. Unauthenticated request -> 401
    res_unauth = client.get("/api/traces")
    assert res_unauth.status_code == 401

    # 2. Normal user (e.g. anil@gmail.com) -> 403 Forbidden
    norm_email = f"normal_user_{uuid.uuid4().hex[:6]}@example.com"
    res_signup = client.post("/api/auth/signup", json={
        "name": "Normal User",
        "email": norm_email,
        "password": "Password123",
        "confirm_password": "Password123",
    })
    assert res_signup.status_code == 200
    normal_token = res_signup.json()["token"]

    res_forbidden = client.get("/api/traces", headers={"Authorization": f"Bearer {normal_token}"})
    assert res_forbidden.status_code == 403
    assert "restricted to administrators" in res_forbidden.json()["detail"].lower()

    # 3. Admin user (admin@gmail.com) -> 200 OK
    admin_token = get_admin_token()
    res_admin = client.get("/api/traces", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200


def test_api_traces_endpoints():
    """Test HTTP API endpoints for /api/traces with admin credentials."""
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Fetch LangSmith config
    res_cfg = client.get("/api/traces/config/langsmith", headers=headers)
    assert res_cfg.status_code == 200
    cfg_data = res_cfg.json()
    assert "langsmith_installed" in cfg_data
    assert "langsmith_active" in cfg_data

    # 2. List traces
    res_list = client.get("/api/traces?limit=10", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert "total" in list_data
    assert isinstance(list_data["traces"], list)

    # 3. Users list endpoint (user-wise breakdown)
    res_users = client.get("/api/traces/users", headers=headers)
    assert res_users.status_code == 200
    assert "users" in res_users.json()

    # 4. Observability stats endpoint
    res_stats = client.get("/api/traces/stats", headers=headers)
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert "total_runs" in stats
    assert "success_rate" in stats

    # 5. If traces exist, fetch specific trace
    if list_data["traces"]:
        sample_id = list_data["traces"][0]["trace_id"]
        res_single = client.get(f"/api/traces/{sample_id}", headers=headers)
        assert res_single.status_code == 200
        single_data = res_single.json()
        assert single_data["trace_id"] == sample_id
        assert "spans" in single_data

    # 6. Non-existent trace returns 404
    res_not_found = client.get("/api/traces/non-existent-uuid-999", headers=headers)
    assert res_not_found.status_code == 404


def test_logger_adapter():
    """Verify contextual logger adapter injects trace metadata."""
    logger = get_logger("test_module")
    # Should not crash when no trace is active
    logger.info("Log outside trace")

    with TraceCollector(session_id="log-sess-1", user_id="log-user-1") as trace:
        trace.record_agent_invocation("supervisor")
        # Should execute smoothly with trace context
        logger.info("Log inside active trace")


def test_end_to_end_chat_trace_creation():
    """Verify chat API creates traces associated with the user, visible only to admin."""
    from unittest.mock import patch, AsyncMock
    import uuid
    suffix = uuid.uuid4().hex[:6]
    test_email = f"trace_user_{suffix}@example.com"

    # 1. Sign up normal user
    res_signup = client.post("/api/auth/signup", json={
        "name": "Tracing Test User",
        "email": test_email,
        "password": "Password123",
        "confirm_password": "Password123",
    })
    assert res_signup.status_code == 200
    token = res_signup.json()["token"]
    user_id = res_signup.json()["user"]["id"]

    # 2. Send chat request (patching run to avoid external LLM network latency in tests)
    with patch("backend.api.routes.run", new_callable=AsyncMock):
        res_chat = client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Show me 2-sharing PGs in Bangalore under 15000"},
        )
        assert res_chat.status_code == 200
        session_id = res_chat.json()["session_id"]
        assert session_id

    # 3. Normal user attempting to access traces gets 403 Forbidden
    res_user_forbidden = client.get(f"/api/traces?user_id={user_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_user_forbidden.status_code == 403

    # 4. Admin queries traces filtered by this user -> 200 OK
    admin_token = get_admin_token()
    res_traces = client.get(f"/api/traces?user_id={user_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_traces.status_code == 200
    traces_data = res_traces.json()
    assert traces_data["total"] >= 1
    user_trace = traces_data["traces"][0]
    assert user_trace["user_email"] == test_email
    assert user_trace["session_id"] == session_id
    assert user_trace["endpoint"] == "/api/chat"
    assert "Show me 2-sharing PGs" in user_trace["user_input"]

