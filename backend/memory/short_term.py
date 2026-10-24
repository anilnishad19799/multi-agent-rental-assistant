"""Short-term memory — thread-safe, per-session in-memory store.

This is the working memory of the system. Each thread (session) gets its own
isolated memory space protected by an asyncio.Lock. Memory is organized into:

  - conversation_buffer: Sliding window of recent messages
  - working_memory:      Current task state (active agent, extracted data so far)
  - attention:           What the user is currently focused on (latest topic/intent)
  - metadata:            Session-level info (conversation_id, user_id, timestamps)
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Maximum messages to keep in the conversation buffer
MAX_BUFFER_SIZE = 100


class ThreadMemory:
    """Thread-safe short-term memory scoped by thread_id (session_id).

    Every read/write acquires an asyncio.Lock for the thread so concurrent
    agent calls within the same session cannot corrupt state.
    """

    _threads: Dict[str, Dict[str, Any]] = {}
    _locks: Dict[str, asyncio.Lock] = {}

    # ── Initialization ────────────────────────────────────────────────

    @classmethod
    def _get_lock(cls, thread_id: str) -> asyncio.Lock:
        if thread_id not in cls._locks:
            cls._locks[thread_id] = asyncio.Lock()
        return cls._locks[thread_id]

    @classmethod
    def _default_state(cls) -> dict:
        return {
            "conversation_buffer": [],
            "working_memory": {
                "current_agent": "supervisor",
                "agent_history": [],
                "extracted_data": {},
                "user_profile": {},
                "search_criteria": {},
                "booking_state": {},
            },
            "attention": {
                "current_topic": None,
                "current_intent": None,
                "last_agent": None,
            },
            "metadata": {
                "conversation_id": None,
                "user_id": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "turn_count": 0,
            },
        }

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self._lock = self._get_lock(thread_id)
        if thread_id not in self._threads:
            self._threads[thread_id] = self._default_state()

    @property
    def _data(self) -> dict:
        return self._threads[self.thread_id]

    # ── Conversation Buffer ───────────────────────────────────────────

    async def add_message(
        self, role: str, content: str, agent: Optional[str] = None
    ) -> None:
        """Append a message to the conversation buffer (thread-safe)."""
        async with self._lock:
            msg = {
                "role": role,
                "content": content,
                "agent": agent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._data["conversation_buffer"].append(msg)

            # Sliding window — keep only the last MAX_BUFFER_SIZE messages
            if len(self._data["conversation_buffer"]) > MAX_BUFFER_SIZE:
                self._data["conversation_buffer"] = (
                    self._data["conversation_buffer"][-MAX_BUFFER_SIZE:]
                )

            # Increment turn count for user messages
            if role == "user":
                self._data["metadata"]["turn_count"] += 1

    async def get_messages(self, limit: int = 20) -> List[dict]:
        """Return the last N messages from the buffer."""
        async with self._lock:
            return list(self._data["conversation_buffer"][-limit:])

    async def get_all_messages(self) -> List[dict]:
        """Return the full conversation buffer."""
        async with self._lock:
            return list(self._data["conversation_buffer"])

    # ── Working Memory (current task state) ───────────────────────────

    async def get(self, key: str) -> Any:
        """Get a value from working memory or metadata."""
        async with self._lock:
            # Check working_memory first, then metadata, then top-level
            wm = self._data["working_memory"]
            if key in wm:
                return wm[key]
            meta = self._data["metadata"]
            if key in meta:
                return meta[key]
            return self._data.get(key)

    async def set(self, key: str, value: Any) -> None:
        """Set a value in working memory."""
        async with self._lock:
            # Route to the right sub-dict
            if key in ("conversation_id", "user_id", "turn_count", "created_at"):
                self._data["metadata"][key] = value
            elif key in ("current_topic", "current_intent", "last_agent"):
                self._data["attention"][key] = value
            else:
                self._data["working_memory"][key] = value

    async def update_dict(self, key: str, updates: dict) -> None:
        """Merge updates into an existing dict in working memory (thread-safe)."""
        async with self._lock:
            wm = self._data["working_memory"]
            current = wm.get(key, {})
            if not isinstance(current, dict):
                current = {}
            current.update({k: v for k, v in updates.items() if v is not None})
            wm[key] = current

    # ── Attention (current focus) ─────────────────────────────────────

    async def set_attention(
        self, topic: Optional[str] = None, intent: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> None:
        """Update what the user is currently focused on."""
        async with self._lock:
            att = self._data["attention"]
            if topic is not None:
                att["current_topic"] = topic
            if intent is not None:
                att["current_intent"] = intent
            if agent is not None:
                att["last_agent"] = agent

    async def get_attention(self) -> dict:
        async with self._lock:
            return dict(self._data["attention"])

    # ── Full Context Snapshot ─────────────────────────────────────────

    async def get_full_context(self) -> dict:
        """Return a deep copy of the full thread state for context building."""
        async with self._lock:
            wm = dict(self._data["working_memory"])
            # Flatten for backward compatibility
            result = dict(wm)
            result["messages"] = list(self._data["conversation_buffer"][-20:])
            result["attention"] = dict(self._data["attention"])
            result["metadata"] = dict(self._data["metadata"])
            return result

    # ── Cleanup ───────────────────────────────────────────────────────

    async def clear(self) -> None:
        """Reset thread memory to defaults."""
        async with self._lock:
            self._threads[self.thread_id] = self._default_state()

    @classmethod
    async def cleanup_thread(cls, thread_id: str) -> None:
        """Remove thread memory entirely."""
        lock = cls._get_lock(thread_id)
        async with lock:
            cls._threads.pop(thread_id, None)
        cls._locks.pop(thread_id, None)
        logger.info(f"Cleaned up thread memory for {thread_id}")

    @classmethod
    def active_threads(cls) -> int:
        return len(cls._threads)

    # ── Legacy Aliases (backward compat with ShortTermMemory) ─────────

    async def append_message(
        self, role: str, content: str, agent: Optional[str] = None
    ) -> None:
        """Alias for add_message — backward compatibility."""
        await self.add_message(role, content, agent)


# Backward-compatible alias
ShortTermMemory = ThreadMemory
