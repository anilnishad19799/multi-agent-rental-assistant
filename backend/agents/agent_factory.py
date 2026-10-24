"""Agent Factory — creates agents using Factory + Registry pattern."""
import logging
from typing import Dict, List, Optional, Type
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AgentFactory:
    """Factory for creating agent instances. Agents register via decorator."""

    _registry: Dict[str, Type[BaseAgent]] = {}

    @classmethod
    def register_agent(cls, name: str):
        """Decorator to register an agent class by name."""
        def wrapper(agent_cls: Type[BaseAgent]):
            cls._registry[name.lower()] = agent_cls
            logger.info(f"Registered agent: {name}")
            return agent_cls
        return wrapper

    @classmethod
    def create_agent(
        cls, agent_name: str, session_id: str, provider: str = None
    ) -> BaseAgent:
        """Create an agent instance by name. Falls back to 'general'."""
        agent_cls = cls._registry.get(agent_name.lower())
        if not agent_cls:
            logger.warning(f"Unknown agent '{agent_name}', falling back to 'general'")
            agent_cls = cls._registry.get("general")
            if not agent_cls:
                raise ValueError(f"No agent registered for '{agent_name}' and no fallback 'general' agent")

        return agent_cls(session_id=session_id, provider=provider)

    @classmethod
    def list_agents(cls) -> List[str]:
        return list(cls._registry.keys())
