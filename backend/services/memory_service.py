"""High-level memory service combining short-term + long-term memory."""
import logging
from typing import Any, Dict, List, Optional
from backend.memory.short_term import ShortTermMemory
from backend.memory.long_term import LongTermMemory

logger = logging.getLogger(__name__)


class MemoryService:
    """Unified memory service for agents to store/retrieve data."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.short_term = ShortTermMemory(session_id)
        self.long_term = LongTermMemory()

    async def initialize(self) -> None:
        """Initialize memory for a new session."""
        logger.info(f"Memory initialized for session {self.session_id}")

    async def store_user_message(self, content: str) -> None:
        await self.short_term.append_message("user", content)

    async def store_agent_response(self, agent_name: str, content: str) -> None:
        await self.short_term.append_message("assistant", content, agent=agent_name)

    async def get_context_for_agent(self, agent_name: str) -> dict:
        context = await self.short_term.get_full_context()
        context["agent_name"] = agent_name
        return context

    async def save_extracted_data(self, agent_name: str, data: dict) -> None:
        await self.short_term.update_dict("extracted_data", data)

        # Also persist to long-term
        conversation_id = await self.short_term.get("conversation_id")
        if conversation_id:
            for key, value in data.items():
                if value is not None and key != "missing_fields":
                    await self.long_term.save_conversation_memory(
                        conversation_id, key, str(value)
                    )

    async def get_conversation_history(self, limit: int = 20) -> List[dict]:
        return await self.short_term.get_messages(limit=limit)

    async def persist_to_db(self) -> None:
        """Persist short-term data to long-term storage."""
        conversation_id = await self.short_term.get("conversation_id")
        if not conversation_id:
            return

        extracted = await self.short_term.get("extracted_data") or {}
        for key, value in extracted.items():
            if value is not None:
                await self.long_term.save_conversation_memory(
                    conversation_id, key, str(value)
                )

        user_profile = await self.short_term.get("user_profile") or {}
        if user_profile:
            await self.long_term.save_user_profile(user_profile)

        logger.info(f"Persisted session data to DB for {self.session_id}")
