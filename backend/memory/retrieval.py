"""Context Retriever — assembles the full LLM context from short-term + long-term memory.

This is the bridge between memory and agents. It combines:
  - Short-term thread memory (conversation buffer, working state)
  - Long-term semantic memory (known facts)
  - Long-term episodic memory (what happened)
  - Long-term procedural memory (learned patterns)
into a single context string that gets injected into the agent's system prompt.
"""
import logging
from typing import Optional

from backend.memory.short_term import ThreadMemory
from backend.memory.long_term import LongTermMemory

logger = logging.getLogger(__name__)


class ContextRetriever:
    """Builds full agent context from short-term thread state + long-term DB memory."""

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.thread_mem = ThreadMemory(thread_id)
        self.long_term = LongTermMemory()

    async def build_context(self, agent_name: str) -> dict:
        """Return a dict with everything the agent needs."""
        context = await self.thread_mem.get_full_context()
        context["agent_name"] = agent_name

        # Enrich with long-term memory
        user_id = await self.thread_mem.get("user_id")
        lt_context = await self.long_term.build_context(
            thread_id=self.thread_id, user_id=user_id,
        )
        context["long_term_context"] = lt_context

        return context

    async def build_context_string(self, agent_name: str) -> str:
        """Build a formatted string for injection into an LLM system prompt.

        Combines:
          1. Conversation history from the thread buffer
          2. Extracted data so far (from working memory)
          3. User profile facts (from working memory + semantic memory)
          4. Search criteria (from working memory + semantic memory)
          5. Long-term memory context (semantic + episodic + procedural)
        """
        parts = []

        # ── 1. Recent conversation history (from thread buffer) ───────
        history = await self.get_conversation_summary(max_messages=10)
        if history and history != "No previous conversation history.":
            parts.append(f"CONVERSATION HISTORY:\n{history}")

        # ── 2. Extracted data so far (working memory) ─────────────────
        extracted_summary = await self.get_extracted_data_summary()
        if extracted_summary and extracted_summary != "No data extracted yet.":
            parts.append(f"EXTRACTED DATA:\n{extracted_summary}")

        # ── 3. User profile (working memory) ─────────────────────────
        profile = await self.thread_mem.get("user_profile") or {}
        if profile:
            profile_str = "\n".join(
                f"  - {k}: {v}" for k, v in profile.items() if v
            )
            if profile_str:
                parts.append(f"USER PROFILE:\n{profile_str}")

        # ── 4. Search criteria (working memory) ──────────────────────
        criteria = await self.thread_mem.get("search_criteria") or {}
        if criteria:
            criteria_str = "\n".join(
                f"  - {k}: {v}" for k, v in criteria.items() if v
            )
            if criteria_str:
                parts.append(f"SEARCH CRITERIA:\n{criteria_str}")

        # ── 5. Long-term memory (semantic + episodic + procedural) ───
        user_id = await self.thread_mem.get("user_id")
        lt_context = await self.long_term.build_context(
            thread_id=self.thread_id, user_id=user_id,
        )
        if lt_context:
            parts.append(lt_context)

        # ── 6. Current attention / focus ─────────────────────────────
        attention = await self.thread_mem.get_attention()
        if attention.get("current_intent"):
            parts.append(
                f"CURRENT FOCUS: intent={attention['current_intent']}, "
                f"topic={attention.get('current_topic', 'N/A')}"
            )

        return "\n\n".join(parts) if parts else ""

    # ── Helper: format conversation buffer ────────────────────────────

    async def get_conversation_summary(self, max_messages: int = 10) -> str:
        """Format recent messages from the thread buffer."""
        messages = await self.thread_mem.get_messages(limit=max_messages)
        if not messages:
            return "No previous conversation history."

        lines = []
        for msg in messages:
            role = msg.get("role", "unknown").capitalize()
            agent = msg.get("agent")
            prefix = f"{role}" + (f" ({agent})" if agent else "")
            content = msg.get("content", "")
            # Truncate long messages in context
            if len(content) > 300:
                content = content[:300] + "..."
            lines.append(f"  {prefix}: {content}")

        return "\n".join(lines)

    async def get_extracted_data_summary(self) -> str:
        """Format all data extracted so far from working memory."""
        data = await self.thread_mem.get("extracted_data") or {}
        if not data:
            return "No data extracted yet."

        lines = [f"  - {k}: {v}" for k, v in data.items() if v is not None]
        return "\n".join(lines) if lines else "No data extracted yet."
