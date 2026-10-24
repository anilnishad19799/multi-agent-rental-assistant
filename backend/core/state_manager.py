"""State manager — tracks conversation state across agent handoffs."""
import logging
from backend.memory.short_term import ShortTermMemory

logger = logging.getLogger(__name__)


class StateManager:
    """Tracks conversation state for multi-agent handoffs."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.memory = ShortTermMemory(session_id)

    async def get_current_agent(self) -> str:
        return await self.memory.get("current_agent") or "supervisor"

    async def set_current_agent(self, agent_name: str) -> None:
        await self.memory.set("current_agent", agent_name)
        # Track history
        history = await self.memory.get("agent_history") or []
        history.append(agent_name)
        await self.memory.set("agent_history", history)

    async def get_conversation_state(self) -> dict:
        return await self.memory.get_full_context()

    async def update_state(self, updates: dict) -> None:
        for key, value in updates.items():
            await self.memory.set(key, value)

    async def should_continue(self) -> bool:
        """Check whether more agent steps are needed (prevent infinite loops)."""
        history = await self.memory.get("agent_history") or []
        return len(history) < 5  # MAX_HANDOFFS
