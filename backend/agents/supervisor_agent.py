"""Supervisor Agent — routes queries using structured LLM output."""
import logging
from backend.agents.base_agent import BaseAgent, AgentResult
from backend.agents.agent_factory import AgentFactory
from backend.agents.prompts import SUPERVISOR_SYSTEM_PROMPT
from backend.agents.schemas import SupervisorDecision
from backend.services.llm.llm_factory import LLMFactory

logger = logging.getLogger(__name__)


@AgentFactory.register_agent("supervisor")
class SupervisorAgent(BaseAgent):
    """Entry point agent that analyzes queries and routes to specialists.

    Uses structured output to get a validated SupervisorDecision —
    no JSON parsing, guaranteed valid routing.
    """

    def __init__(self, session_id: str, provider: str = None):
        super().__init__(
            agent_name="supervisor",
            session_id=session_id,
            provider=provider,
        )

    def get_system_prompt(self) -> str:
        return SUPERVISOR_SYSTEM_PROMPT

    async def process(self, user_input: str, context: dict) -> AgentResult:
        """Analyze user query and decide which agent should handle it.

        Uses structured_output() to get a typed SupervisorDecision
        with guaranteed valid target_agent enum value.
        """
        # Use structured output — the LLM is constrained to return
        # a valid SupervisorDecision with target_agent as an enum
        decision: SupervisorDecision = await self.extract_structured_data(
            user_input=user_input,
            context=context,
            schema=SupervisorDecision,
        )

        target_agent = decision.target_agent.value
        reasoning = decision.reasoning
        intent = decision.extracted_intent

        logger.info(
            f"Supervisor routing: '{user_input[:50]}...' → {target_agent} "
            f"(reason: {reasoning})"
        )

        return AgentResult(
            agent_name="supervisor",
            response_text="",  # Supervisor doesn't respond to user directly
            extracted_data={"intent": intent},
            next_agent=target_agent,
            requires_user_input=False,
            metadata={
                "reasoning": reasoning,
                "routing": decision.model_dump(),
            },
        )
