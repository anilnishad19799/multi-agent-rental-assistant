"""Production tracing and observability system.

Integrates with LangSmith for cloud tracing and provides a local,
persistent trace store with span-level drill-down for API calls,
user requests, agent handoffs, LLM completions, and tool executions.
"""
import asyncio
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError
from backend.models.base import get_session
from backend.models.trace import TraceRecord

logger = logging.getLogger(__name__)

# ── LangSmith Setup ─────────────────────────────────────────────
# Automatically configured via environment variables
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() in ("true", "1")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "real-estate-rental-agent")

try:
    from langsmith import traceable, Client as LangSmithClient
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


# ── Context Variable for Async Flow Tracing ─────────────────────
_active_trace: ContextVar[Optional["TraceCollector"]] = ContextVar("active_trace", default=None)

# In-memory fast ring buffer of recent traces
_recent_traces_cache: deque = deque(maxlen=100)


def get_current_trace() -> Optional["TraceCollector"]:
    """Retrieve the currently active trace collector for this async context."""
    return _active_trace.get()


@dataclass
class TraceSpan:
    name: str
    span_type: str  # "api", "supervisor", "agent", "llm", "tool", "memory"
    start_time: float
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "SUCCESS"  # "SUCCESS", "ERROR"
    inputs: Optional[Any] = None
    outputs: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def finish(self, outputs: Any = None, error: Optional[str] = None, status: Optional[str] = None):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        if outputs is not None:
            self.outputs = outputs
        if error:
            self.error = str(error)
            self.status = "ERROR"
        elif status:
            self.status = status

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "span_type": self.span_type,
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time, tz=timezone.utc).isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "inputs": self._sanitize(self.inputs),
            "outputs": self._sanitize(self.outputs),
            "metadata": self._sanitize(self.metadata),
            "error": self.error,
        }

    def _sanitize(self, val: Any) -> Any:
        if val is None or isinstance(val, (int, float, str, bool)):
            return val
        if isinstance(val, dict):
            return {k: self._sanitize(v) for k, v in val.items()}
        if isinstance(val, (list, tuple)):
            return [self._sanitize(v) for v in val]
        return str(val)


class TraceCollector:
    """Collects spans, agent transitions, and LLM metrics for a single request lifecycle."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        endpoint: str = "/api/chat",
        user_input: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.trace_id = str(uuid.uuid4())
        self.session_id = session_id
        self.user_id = user_id
        self.user_email = user_email
        self.endpoint = endpoint
        self.user_input = user_input
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.status = "SUCCESS"
        self.agents_invoked: List[str] = []
        self.agent_response: Optional[str] = None
        self.error_message: Optional[str] = None
        self.spans: List[TraceSpan] = []
        self.metadata = metadata or {}
        self._token = None
        self._finished = False
        self.register_in_cache()

    def register_in_cache(self):
        """Register or update current trace snapshot in the fast recent-traces cache."""
        summary = self.to_dict()
        for idx, t in enumerate(_recent_traces_cache):
            if t.get("trace_id") == self.trace_id:
                _recent_traces_cache[idx] = summary
                return
        _recent_traces_cache.appendleft(summary)

    def __enter__(self):
        self._token = _active_trace.set(self)
        self.register_in_cache()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val and not self.error_message:
            self.status = "ERROR"
            self.error_message = str(exc_val)
        if not self._finished:
            self.finish()
        if self._token:
            _active_trace.reset(self._token)

    def start_span(
        self,
        name: str,
        span_type: str,
        inputs: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """Begin a new child span."""
        span = TraceSpan(
            name=name,
            span_type=span_type,
            start_time=time.time(),
            inputs=inputs,
            metadata=metadata or {},
        )
        self.spans.append(span)
        return span

    def record_agent_invocation(self, agent_name: str):
        """Track which agents were invoked."""
        if agent_name and agent_name not in self.agents_invoked:
            self.agents_invoked.append(agent_name)

    def record_llm_call(
        self,
        provider: str,
        model: str,
        messages: list,
        response: Any,
        duration_ms: float,
        error: Optional[str] = None,
    ):
        """Record an LLM call directly as a span."""
        span = TraceSpan(
            name=f"LLM Call ({provider} / {model})",
            span_type="llm",
            start_time=time.time() - (duration_ms / 1000.0),
            end_time=time.time(),
            duration_ms=round(duration_ms, 2),
            status="ERROR" if error else "SUCCESS",
            inputs={"messages": messages, "model": model, "provider": provider},
            outputs=response,
            metadata={"provider": provider, "model": model},
            error=error,
        )
        self.spans.append(span)

    def finish(
        self,
        agent_response: Optional[str] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """Finalize the trace collector and persist."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        if agent_response is not None:
            self.agent_response = agent_response
        if error:
            self.error_message = str(error)
            self.status = "ERROR"
        elif status:
            self.status = status

        # Close any unclosed spans
        for s in self.spans:
            if s.end_time is None:
                s.finish()

        # Cache in memory
        self.register_in_cache()
        self._finished = True

        # Async fire-and-forget save to SQLite DB
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist_to_db())
        except RuntimeError:
            pass

    async def _persist_to_db(self):
        """Persist trace record to SQLite database with safe upsert."""
        try:
            async with get_session() as session:
                stmt = select(TraceRecord).where(TraceRecord.trace_id == self.trace_id)
                res = await session.execute(stmt)
                existing = res.scalar_one_or_none()

                spans_json = json.dumps([s.to_dict() for s in self.spans])
                meta_json = json.dumps(self.metadata)
                response_sample = self.agent_response[:1000] if self.agent_response else None

                if existing:
                    existing.status = self.status
                    existing.duration_ms = self.duration_ms
                    existing.agents_invoked = ",".join(self.agents_invoked)
                    existing.agent_response = response_sample
                    existing.error_message = self.error_message
                    existing.spans = spans_json
                    existing.metadata_json = meta_json
                else:
                    rec = TraceRecord(
                        trace_id=self.trace_id,
                        session_id=self.session_id,
                        user_id=self.user_id,
                        user_email=self.user_email,
                        endpoint=self.endpoint,
                        status=self.status,
                        duration_ms=self.duration_ms,
                        agents_invoked=",".join(self.agents_invoked),
                        user_input=self.user_input,
                        agent_response=response_sample,
                        error_message=self.error_message,
                        spans=spans_json,
                        metadata_json=meta_json,
                    )
                    session.add(rec)
                await session.commit()
                logger.info(f"Persisted trace {self.trace_id} ({self.duration_ms}ms) with {len(self.spans)} spans")
        except IntegrityError:
            # Race condition recovery: update existing record instead of throwing UNIQUE constraint error
            try:
                async with get_session() as session:
                    stmt = select(TraceRecord).where(TraceRecord.trace_id == self.trace_id)
                    res = await session.execute(stmt)
                    existing = res.scalar_one_or_none()
                    if existing:
                        existing.status = self.status
                        existing.duration_ms = self.duration_ms
                        existing.agents_invoked = ",".join(self.agents_invoked)
                        existing.agent_response = self.agent_response[:1000] if self.agent_response else None
                        existing.error_message = self.error_message
                        existing.spans = json.dumps([s.to_dict() for s in self.spans])
                        existing.metadata_json = json.dumps(self.metadata)
                        await session.commit()
            except Exception as e2:
                logger.warning(f"Secondary trace update ignored: {e2}")
        except Exception as e:
            logger.error(f"Failed to persist trace {self.trace_id}: {e}", exc_info=True)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "endpoint": self.endpoint,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time, tz=timezone.utc).isoformat() if self.end_time else None,
            "agents_invoked": self.agents_invoked,
            "user_input": self.user_input,
            "agent_response": self.agent_response,
            "error_message": self.error_message,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
        }


# ── Query APIs ──────────────────────────────────────────────────

async def get_recent_traces(
    limit: int = 50,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    agent: Optional[str] = None,
    status: Optional[str] = None,
) -> List[dict]:
    """Retrieve recent traces filtered by user ID, user email, agent, or status."""
    # Try querying SQLite database first for persistence
    try:
        async with get_session() as session:
            stmt = select(TraceRecord).order_by(desc(TraceRecord.created_at))
            if user_id:
                stmt = stmt.where(TraceRecord.user_id == user_id)
            if user_email:
                stmt = stmt.where(TraceRecord.user_email == user_email)
            if status:
                stmt = stmt.where(TraceRecord.status == status)

            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            records = result.scalars().all()

            if records:
                traces = []
                for r in records:
                    agents_list = [a.strip() for a in (r.agents_invoked or "").split(",") if a.strip()]
                    if agent and agent not in agents_list:
                        continue
                    try:
                        spans_list = json.loads(r.spans) if r.spans else []
                    except Exception:
                        spans_list = []
                    try:
                        meta = json.loads(r.metadata_json) if r.metadata_json else {}
                    except Exception:
                        meta = {}

                    traces.append({
                        "trace_id": r.trace_id,
                        "session_id": r.session_id,
                        "user_id": r.user_id,
                        "user_email": r.user_email,
                        "endpoint": r.endpoint,
                        "status": r.status,
                        "duration_ms": r.duration_ms,
                        "start_time": r.created_at.isoformat() if r.created_at else None,
                        "agents_invoked": agents_list,
                        "user_input": r.user_input,
                        "agent_response": r.agent_response,
                        "error_message": r.error_message,
                        "span_count": len(spans_list),
                        "spans": spans_list,
                        "metadata": meta,
                    })
                return traces
    except Exception as e:
        logger.warning(f"DB trace fetch failed, falling back to in-memory cache: {e}")

    # Fallback to in-memory cache
    results = list(_recent_traces_cache)
    if user_id:
        results = [t for t in results if t.get("user_id") == user_id]
    if user_email:
        results = [t for t in results if t.get("user_email") == user_email]
    if agent:
        results = [t for t in results if agent in t.get("agents_invoked", [])]
    if status:
        results = [t for t in results if t.get("status") == status]
    return results[:limit]


async def get_trace_by_id(trace_id: str) -> Optional[dict]:
    """Retrieve full trace details and span hierarchy by trace_id."""
    # Check in-memory first
    for t in _recent_traces_cache:
        if t.get("trace_id") == trace_id:
            return t

    # Check DB
    try:
        async with get_session() as session:
            stmt = select(TraceRecord).where(TraceRecord.trace_id == trace_id)
            result = await session.execute(stmt)
            r = result.scalar_one_or_none()
            if not r:
                return None
            return {
                "trace_id": r.trace_id,
                "session_id": r.session_id,
                "user_id": r.user_id,
                "user_email": r.user_email,
                "endpoint": r.endpoint,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "start_time": r.created_at.isoformat() if r.created_at else None,
                "agents_invoked": [a.strip() for a in (r.agents_invoked or "").split(",") if a.strip()],
                "user_input": r.user_input,
                "agent_response": r.agent_response,
                "error_message": r.error_message,
                "spans": json.loads(r.spans) if r.spans else [],
                "metadata": json.loads(r.metadata_json) if r.metadata_json else {},
            }
    except Exception as e:
        logger.error(f"Error reading trace {trace_id}: {e}")
        return None


def get_langsmith_info() -> dict:
    """Return LangSmith cloud integration status and project details."""
    is_active = bool(LANGCHAIN_TRACING_V2 and LANGCHAIN_API_KEY)
    return {
        "langsmith_installed": LANGSMITH_AVAILABLE,
        "langsmith_active": is_active,
        "project": LANGCHAIN_PROJECT if is_active else None,
        "endpoint": os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
        "dashboard_url": f"https://smith.langchain.com/o/projects/{LANGCHAIN_PROJECT}" if is_active else "https://smith.langchain.com",
        "instructions": (
            "To send traces to LangSmith cloud, set LANGCHAIN_TRACING_V2=true and "
            "LANGCHAIN_API_KEY=lsv2_pt_... in your .env file."
        ) if not is_active else "LangSmith cloud tracing is actively capturing traces."
    }


async def get_distinct_users_with_traces() -> List[dict]:
    """Return all distinct users that have generated traces, with trace count and last active time."""
    users_map = {}
    try:
        async with get_session() as session:
            stmt = select(TraceRecord).order_by(desc(TraceRecord.created_at))
            result = await session.execute(stmt)
            records = result.scalars().all()
            for r in records:
                user_key = r.user_email or r.user_id or "anonymous"
                if user_key not in users_map:
                    users_map[user_key] = {
                        "user_id": r.user_id,
                        "user_email": r.user_email or (r.user_id if "@" in (r.user_id or "") else "anonymous"),
                        "trace_count": 0,
                        "last_active": r.created_at.isoformat() if r.created_at else None,
                    }
                users_map[user_key]["trace_count"] += 1
    except Exception as e:
        logger.warning(f"Error querying distinct trace users from DB: {e}")

    # Fallback / merge with in-memory cache
    for t in _recent_traces_cache:
        user_key = t.get("user_email") or t.get("user_id") or "anonymous"
        if user_key not in users_map:
            users_map[user_key] = {
                "user_id": t.get("user_id"),
                "user_email": t.get("user_email") or "anonymous",
                "trace_count": 1,
                "last_active": t.get("start_time"),
            }

    return list(users_map.values())


async def get_traces_summary_stats() -> dict:
    """Calculate aggregate observability statistics for the admin dashboard."""
    traces = await get_recent_traces(limit=200)
    total = len(traces)
    if total == 0:
        return {
            "total_runs": 0,
            "success_count": 0,
            "error_count": 0,
            "success_rate": 100.0,
            "avg_latency_ms": 0,
            "users_count": 0,
            "agent_distribution": {},
        }

    success_count = sum(1 for t in traces if t.get("status") == "SUCCESS")
    error_count = total - success_count
    success_rate = round((success_count / total) * 100, 1)
    avg_latency = round(sum(t.get("duration_ms", 0) for t in traces) / total, 1)

    unique_users = set(
        t.get("user_email") or t.get("user_id")
        for t in traces
        if (t.get("user_email") or t.get("user_id"))
    )
    agent_dist = {}
    for t in traces:
        for a in t.get("agents_invoked", []):
            agent_dist[a] = agent_dist.get(a, 0) + 1

    return {
        "total_runs": total,
        "success_count": success_count,
        "error_count": error_count,
        "success_rate": success_rate,
        "avg_latency_ms": avg_latency,
        "users_count": len(unique_users),
        "agent_distribution": agent_dist,
    }
