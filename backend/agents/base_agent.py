"""Base agent abstraction + AgentResult dataclass + AgentMemory.

AgentMemory now properly integrates:
  - ThreadMemory  (short-term, per-session, thread-safe)
  - LongTermMemory (persistent: semantic + episodic + procedural)
  - ContextRetriever (assembles full context for LLM prompts)
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from backend.events.publisher import publish_event
from backend.events.types import EventType
from backend.memory.short_term import ThreadMemory
from backend.memory.long_term import LongTermMemory
from backend.memory.retrieval import ContextRetriever
from backend.services.llm.llm_factory import LLMFactory
from backend.observability.tracing import get_current_trace, traceable

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class AgentResult:
    """Structured result returned by every agent."""
    agent_name: str
    response_text: str
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    next_agent: Optional[str] = None  # for supervisor routing
    requires_user_input: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentMemory:
    """Per-agent memory — bridges short-term thread state and long-term DB stores.

    Short-term (ThreadMemory):
      - conversation_buffer: sliding window of messages
      - working_memory: extracted_data, user_profile, search_criteria, current_agent
      - attention: current topic/intent focus

    Long-term (LongTermMemory):
      - semantic: facts (user_name=Rahul, city=Pune)
      - episodic: events (user searched at 3pm, agent handed off)
      - procedural: patterns (user prefers 2-sharing, always asks budget first)
    """

    def __init__(self, agent_name: str, thread_id: str):
        self.agent_name = agent_name
        self.thread_id = thread_id
        self.thread = ThreadMemory(thread_id)
        self.long_term = LongTermMemory()
        self._retriever = ContextRetriever(thread_id)

    # ── Short-term: Thread Memory ─────────────────────────────────────

    async def get(self, key: str) -> Any:
        """Read from thread working memory."""
        return await self.thread.get(key)

    async def set(self, key: str, value: Any) -> None:
        """Write to thread working memory."""
        await self.thread.set(key, value)

    async def update_dict(self, key: str, updates: dict) -> None:
        """Merge updates into a dict in working memory."""
        await self.thread.update_dict(key, updates)

    async def add_message(
        self, role: str, content: str, agent: Optional[str] = None,
    ) -> None:
        """Append a message to the thread conversation buffer."""
        await self.thread.add_message(role, content, agent)

    async def get_messages(self, limit: int = 20) -> List[dict]:
        """Get recent messages from the thread buffer."""
        return await self.thread.get_messages(limit)

    async def set_attention(
        self, topic: str = None, intent: str = None,
    ) -> None:
        """Update what the user is currently focused on."""
        await self.thread.set_attention(
            topic=topic, intent=intent, agent=self.agent_name,
        )

    # ── Long-term: Semantic Memory (facts) ────────────────────────────

    async def store_fact(
        self, entity_type: str, key: str, value: str,
        confidence: float = 1.0,
    ) -> None:
        """Store a single fact to semantic memory."""
        user_id = await self.thread.get("user_id")
        await self.long_term.semantic.store_fact(
            entity_type=entity_type,
            fact_key=key,
            fact_value=value,
            thread_id=self.thread_id,
            user_id=user_id,
            source_agent=self.agent_name,
            confidence=confidence,
        )

    async def get_fact(self, entity_type: str, key: str) -> Optional[str]:
        """Retrieve a single fact from semantic memory."""
        user_id = await self.thread.get("user_id")
        return await self.long_term.semantic.get_fact(
            entity_type, key, user_id=user_id, thread_id=self.thread_id,
        )

    # ── Long-term: Episodic Memory (events) ───────────────────────────

    async def record_event(
        self, episode_type: str, action: str, content: str = None,
        outcome: str = None, data_snapshot: dict = None,
    ) -> None:
        """Record an event/episode to episodic memory."""
        user_id = await self.thread.get("user_id")
        await self.long_term.episodic.record_event(
            thread_id=self.thread_id,
            episode_type=episode_type,
            action=action,
            content=content,
            actor=self.agent_name,
            outcome=outcome,
            data_snapshot=data_snapshot,
            user_id=user_id,
        )

    # ── Long-term: Procedural Memory (patterns) ──────────────────────

    async def record_preference(self, key: str, value: str) -> None:
        """Record a learned user preference."""
        user_id = await self.thread.get("user_id")
        await self.long_term.procedural.record_preference(key, value, user_id)

    # ── Context Building ─────────────────────────────────────────────

    async def build_context_string(self) -> str:
        """Build full context string for LLM prompt injection.

        Pulls from:
          - Thread buffer (recent messages)
          - Working memory (extracted data, user profile, search criteria)
          - Long-term semantic memory (known facts from DB)
          - Long-term episodic memory (past events from DB)
          - Long-term procedural memory (learned patterns from DB)
        """
        return await self._retriever.build_context_string(self.agent_name)

    async def get_full_context(self) -> dict:
        """Get full thread context as a dict (for passing to agents)."""
        return await self.thread.get_full_context()

    # ── Backward-compatible aliases ──────────────────────────────────

    @property
    def short_term(self):
        """Alias for backward compat — returns the ThreadMemory instance."""
        return self.thread

    async def append_message(
        self, role: str, content: str, agent: Optional[str] = None,
    ) -> None:
        """Alias for add_message."""
        await self.add_message(role, content, agent)


class BaseAgent(ABC):
    """Abstract base class for all agents. All agents MUST extend this."""

    def __init__(self, agent_name: str, session_id: str, provider: str = None):
        self.agent_name = agent_name
        self.session_id = session_id
        self.provider = provider
        self.memory = AgentMemory(agent_name, session_id)

    @abstractmethod
    async def process(self, user_input: str, context: dict) -> AgentResult:
        """Process user input and return structured result."""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    def get_extraction_prompt(self) -> str:
        """Return the system prompt used for structured data extraction.

        Override in subclasses to provide a focused extraction-only prompt.
        Defaults to the main system prompt.
        """
        return self.get_system_prompt()

    async def build_messages(self, user_input: str, context: dict) -> list:
        """Build the LLM message list: system prompt + context + history + user input."""
        messages = []

        # System prompt with full memory context
        system_prompt = self.get_system_prompt()
        context_str = await self.memory.build_context_string()
        if context_str:
            system_prompt += f"\n\nCURRENT CONTEXT:\n{context_str}"

        # Inject DB search results if available (used by rent agent)
        db_results = context.get("db_search_results", "")
        if db_results:
            system_prompt += f"\n{db_results}"

        messages.append({"role": "system", "content": system_prompt})

        # Conversation history from thread buffer
        history = await self.memory.get_messages(limit=20)
        for msg in history:
            role = msg.get("role", "user")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": msg.get("content", "")})

        # Current user input
        messages.append({"role": "user", "content": user_input})

        return messages

    async def stream_response(self, user_input: str, context: dict) -> AsyncGenerator[str, None]:
        """Stream LLM response with agent-specific prompt. Publishes SSE events."""
        await publish_event(self.session_id, EventType.AGENT_START, {
            "agent": self.agent_name
        })

        messages = await self.build_messages(user_input, context)

        # Ensure LLM clients are registered
        import backend.services.llm  # noqa: F401

        client = LLMFactory.get_llm_client(self.provider)
        full_response = ""

        trace = get_current_trace()
        span = None
        if trace:
            span = trace.start_span(
                name=f"{self.agent_name.capitalize()} LLM Stream ({self.provider})",
                span_type="llm",
                inputs={"message_count": len(messages), "provider": self.provider},
            )

        try:
            async for token in client.stream(messages):
                full_response += token
                await publish_event(
                    session_id=self.session_id,
                    event_type=EventType.LLM_TOKEN,
                    data={"token": token, "agent": self.agent_name},
                )
                yield token

            await publish_event(self.session_id, EventType.LLM_DONE, {
                "agent": self.agent_name
            })
            if span:
                span.finish(outputs={"response_length": len(full_response), "response_preview": full_response[:300]})

        except asyncio.CancelledError:
            logger.info(f"[{self.agent_name}] LLM streaming cancelled by user")
            if span:
                span.finish(outputs={"response_length": len(full_response), "cancelled": True}, status="STOPPED")
            raise

        except Exception as e:
            logger.error(f"Error streaming from {self.agent_name}: {e}", exc_info=True)
            if span:
                span.finish(error=str(e))
            await publish_event(self.session_id, EventType.ERROR, {
                "error": str(e), "agent": self.agent_name
            })

        # Store agent response in thread memory
        await self.memory.add_message("assistant", full_response, self.agent_name)

    async def extract_structured_data(
        self,
        user_input: str,
        context: dict,
        schema: Type[T],
        agent_response: str = "",
    ) -> T:
        """Extract structured data from conversation using LLM structured output.

        This makes a SEPARATE LLM call specifically for extraction, using
        the provider's native structured output API (response_format / response_schema).
        The LLM returns a validated Pydantic model — NO regex/JSON parsing.

        Args:
            user_input: The user's message
            context: Current conversation context
            schema: Pydantic model class to extract into
            agent_response: The conversational response already generated (for context)

        Returns:
            Validated Pydantic model instance with extracted data
        """
        # Build extraction-focused messages
        extraction_prompt = self.get_extraction_prompt()
        context_str = await self.memory.build_context_string()

        system_content = (
            f"{extraction_prompt}\n\n"
            f"TASK: Extract structured data from the conversation below. "
            f"Fill in all fields you can determine from context. "
            f"Set null for fields not yet known. "
            f"List any required fields that are still missing in missing_fields."
        )

        if context_str:
            system_content += f"\n\nCURRENT CONTEXT:\n{context_str}"

        messages = [{"role": "system", "content": system_content}]

        # Add conversation history from thread
        history = await self.memory.get_messages(limit=20)
        for msg in history:
            role = msg.get("role", "user")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": msg.get("content", "")})

        # Add current user input
        messages.append({"role": "user", "content": user_input})

        # Add the agent's response if available
        if agent_response:
            messages.append({"role": "assistant", "content": agent_response})

        # Call structured output API
        import backend.services.llm  # noqa: F401
        client = LLMFactory.get_llm_client(self.provider)

        trace = get_current_trace()
        span = None
        if trace:
            span = trace.start_span(
                name=f"{self.agent_name.capitalize()} Structured Output ({schema.__name__})",
                span_type="llm",
                inputs={"schema": schema.__name__, "provider": self.provider},
            )

        try:
            result = await client.structured_output(messages, schema)
            logger.info(
                f"[{self.agent_name}] Structured extraction: "
                f"{result.model_dump(exclude_none=True)}"
            )
            if span:
                span.finish(outputs=result.model_dump(exclude_none=True))
            return result

        except Exception as e:
            logger.error(
                f"[{self.agent_name}] Structured output failed: {e}",
                exc_info=True,
            )
            if span:
                span.finish(error=str(e))
            # Re-raise — callers should handle the failure rather than
            # receiving an invalid schema instance with missing fields.
            raise
