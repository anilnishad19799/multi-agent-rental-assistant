"""General Agent — handles greetings, help, and general conversation."""
import logging
from backend.agents.base_agent import BaseAgent, AgentResult
from backend.agents.agent_factory import AgentFactory
from backend.agents.prompts import GENERAL_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@AgentFactory.register_agent("general")
class GeneralAgent(BaseAgent):
    """Handles incomplete queries, follow-ups, greetings, and general questions."""

    def __init__(self, session_id: str, provider: str = None):
        super().__init__(
            agent_name="general",
            session_id=session_id,
            provider=provider,
        )

    def get_system_prompt(self) -> str:
        return GENERAL_AGENT_SYSTEM_PROMPT

    async def process(self, user_input: str, context: dict) -> AgentResult:
        """Stream a conversational response."""
        full_response = ""
        async for token in self.stream_response(user_input, context):
            full_response += token

        return AgentResult(
            agent_name="general",
            response_text=full_response,
            extracted_data={},
            next_agent=None,
            requires_user_input=True,  # general agent always waits for user
            metadata={},
        )
