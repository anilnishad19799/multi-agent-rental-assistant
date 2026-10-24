"""Long-term memory — unified facade over Semantic, Episodic, and Procedural stores.

This is the single entry point for all persistent memory operations.
It composes the three memory types and provides convenience methods that
the orchestrator and agents call.

Memory Types:
  - Semantic:   FACTS about entities (user profile, search criteria, preferences)
  - Episodic:   EVENTS that happened (messages, handoffs, extractions, bookings)
  - Procedural: PATTERNS learned over time (user behaviors, preferences, flows)
"""
import logging
from typing import Any, Dict, List, Optional

from backend.memory.semantic import SemanticMemory
from backend.memory.episodic import EpisodicMemory
from backend.memory.procedural import ProceduralMemory

logger = logging.getLogger(__name__)


class LongTermMemory:
    """Unified facade for all three long-term memory stores.

    Usage:
        ltm = LongTermMemory()

        # Semantic: store/retrieve facts
        await ltm.semantic.store_fact("USER", "name", "Rahul", thread_id=...)
        name = await ltm.semantic.get_fact("USER", "name", thread_id=...)

        # Episodic: record/retrieve events
        await ltm.episodic.record_user_message(thread_id, content)
        episodes = await ltm.episodic.get_thread_episodes(thread_id)

        # Procedural: record/retrieve patterns
        await ltm.procedural.record_preference("budget_sensitivity", "high")
        prefs = await ltm.procedural.get_user_preferences(user_id)

        # Or use the high-level convenience methods below.
    """

    def __init__(self):
        self.semantic = SemanticMemory()
        self.episodic = EpisodicMemory()
        self.procedural = ProceduralMemory()

    # ── Convenience: Save Extracted Data ──────────────────────────────

    async def save_extracted_data(
        self,
        thread_id: str,
        agent_name: str,
        extracted_data: dict,
        user_id: Optional[str] = None,
    ) -> None:
        """Save extracted data to BOTH semantic and episodic memory.

        Semantic: stores each fact (city=Pune, budget=8000)
        Episodic: records the extraction event (agent X extracted Y at time Z)
        """
        # Determine entity type from agent
        entity_type_map = {
            "rent": "SEARCH",
            "user_info": "USER",
            "calendar": "BOOKING",
            "supervisor": "INTENT",
        }
        entity_type = entity_type_map.get(agent_name, "GENERAL")

        # Semantic: store each fact
        await self.semantic.store_facts_batch(
            facts=extracted_data,
            entity_type=entity_type,
            thread_id=thread_id,
            user_id=user_id,
            source_agent=agent_name,
        )

        # Episodic: record the extraction event
        await self.episodic.record_data_extraction(
            thread_id=thread_id,
            agent_name=agent_name,
            extracted_data=extracted_data,
            user_id=user_id,
        )

        logger.info(
            f"[{thread_id}] LTM saved: {len(extracted_data)} facts "
            f"from {agent_name} (semantic+episodic)"
        )

    # ── Convenience: Record Conversation Turn ─────────────────────────

    async def save_turn(
        self,
        thread_id: str,
        user_message: str,
        agent_name: str,
        agent_response: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Record a full conversation turn (user message + agent response) to episodic memory."""
        await self.episodic.record_user_message(thread_id, user_message, user_id)
        if agent_response:
            await self.episodic.record_agent_response(
                thread_id, agent_name, agent_response, user_id,
            )

    # ── Convenience: Record Agent Handoff ─────────────────────────────

    async def save_handoff(
        self,
        thread_id: str,
        from_agent: str,
        to_agent: str,
        reasoning: str = "",
        user_id: Optional[str] = None,
    ) -> None:
        """Record an agent handoff event to episodic memory."""
        await self.episodic.record_agent_handoff(
            thread_id, from_agent, to_agent, reasoning, user_id,
        )

    # ── Convenience: Save User Profile ────────────────────────────────

    async def save_user_profile(
        self,
        thread_id: str,
        profile: dict,
        user_id: Optional[str] = None,
    ) -> None:
        """Persist user profile facts to semantic memory."""
        await self.semantic.store_facts_batch(
            facts=profile,
            entity_type="USER",
            thread_id=thread_id,
            user_id=user_id,
            source_agent="user_info",
        )

    # ── Convenience: Save Search Criteria ─────────────────────────────

    async def save_search_criteria(
        self,
        thread_id: str,
        criteria: dict,
        user_id: Optional[str] = None,
    ) -> None:
        """Persist search criteria to semantic memory."""
        await self.semantic.store_facts_batch(
            facts=criteria,
            entity_type="SEARCH",
            thread_id=thread_id,
            user_id=user_id,
            source_agent="rent",
        )

    # ── Convenience: Learn Patterns ───────────────────────────────────

    async def learn_from_session(
        self,
        thread_id: str,
        agent_history: List[str],
        extracted_data: dict,
        user_id: Optional[str] = None,
    ) -> None:
        """Analyze a completed session and store procedural patterns.

        Called at the end of a conversation to learn from user behavior.
        """
        # Record the agent flow sequence
        if agent_history:
            await self.procedural.record_agent_sequence(agent_history, user_id)

        # Record any search preferences
        criteria = {
            k: v for k, v in extracted_data.items()
            if k in ("city", "area", "property_type", "sharing_type")
            and v is not None
        }
        for key, value in criteria.items():
            await self.procedural.record_preference(key, str(value), user_id)

    # ── Build Full Context ────────────────────────────────────────────

    async def build_context(
        self,
        thread_id: str,
        user_id: Optional[str] = None,
    ) -> str:
        """Build a comprehensive context string from all three memory types.

        This is injected into the agent's system prompt to give it
        full awareness of known facts, past events, and learned patterns.
        """
        parts = []

        # Semantic: what we know
        semantic_ctx = await self.semantic.format_for_context(
            user_id=user_id, thread_id=thread_id,
        )
        if semantic_ctx:
            parts.append(semantic_ctx)

        # Episodic: what happened
        episodic_ctx = await self.episodic.format_for_context(
            thread_id=thread_id, limit=10,
        )
        if episodic_ctx:
            parts.append(episodic_ctx)

        # Procedural: how to behave
        procedural_ctx = await self.procedural.format_for_context(
            user_id=user_id,
        )
        if procedural_ctx:
            parts.append(procedural_ctx)

        return "\n\n".join(parts) if parts else ""
