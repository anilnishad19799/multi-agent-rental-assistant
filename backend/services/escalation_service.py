"""Escalation service — handles agent escalation to human."""
import logging

logger = logging.getLogger(__name__)


class EscalationService:
    """Handles escalation from AI agents to human support."""

    @staticmethod
    async def escalate_to_human(session_id: str, reason: str, context: dict) -> dict:
        """Log an escalation request. In production, this would notify a human agent."""
        logger.warning(f"Escalation requested for session {session_id}: {reason}")
        return {
            "status": "escalated",
            "session_id": session_id,
            "reason": reason,
            "message": "Your request has been escalated to a human agent. They will be in touch shortly.",
        }

    @staticmethod
    async def notify_agent(agent_email: str, message: str) -> bool:
        """Placeholder for email/SMS notification to a real estate agent."""
        logger.info(f"Notification to {agent_email}: {message}")
        # In production: integrate with email/SMS service
        return True
