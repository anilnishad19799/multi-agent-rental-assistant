"""Episodic Memory — stores and retrieves EVENTS and conversation episodes.

Episodic memory answers: "What HAPPENED in this conversation?"

Examples:
  - User sent "Show me PG in Hadapsar under 8000"
  - Supervisor routed to rent agent
  - Rent agent extracted: city=Pune, area=Hadapsar, budget=8000
  - Agent responded with 3 property suggestions
  - User booked a visit for Sept 10 at 2 PM
"""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

from sqlalchemy import select, and_, desc
from backend.models.base import get_session
from backend.models import EpisodicMemoryRecord

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """Stores and retrieves conversation events/episodes in the database."""

    # ── Write ──────────────────────────────────────────────────────────

    async def record_event(
        self,
        thread_id: str,
        episode_type: str,
        action: str,
        content: Optional[str] = None,
        actor: Optional[str] = None,
        outcome: Optional[str] = None,
        data_snapshot: Optional[dict] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Record a single event/episode. Returns the record id."""
        async with get_session() as session:
            record = EpisodicMemoryRecord(
                user_id=user_id,
                thread_id=thread_id,
                episode_type=episode_type,
                actor=actor,
                action=action,
                content=content[:2000] if content else None,  # Cap content length
                outcome=outcome,
                data_snapshot=json.dumps(data_snapshot) if data_snapshot else None,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record.id

    async def record_user_message(
        self, thread_id: str, content: str, user_id: Optional[str] = None,
    ) -> str:
        return await self.record_event(
            thread_id=thread_id,
            episode_type="TURN",
            action="user_message",
            content=content,
            actor="user",
            user_id=user_id,
        )

    async def record_agent_response(
        self, thread_id: str, agent_name: str, content: str,
        user_id: Optional[str] = None,
    ) -> str:
        return await self.record_event(
            thread_id=thread_id,
            episode_type="TURN",
            action="agent_response",
            content=content,
            actor=agent_name,
            user_id=user_id,
        )

    async def record_agent_handoff(
        self, thread_id: str, from_agent: str, to_agent: str,
        reasoning: str = "", user_id: Optional[str] = None,
    ) -> str:
        return await self.record_event(
            thread_id=thread_id,
            episode_type="HANDOFF",
            action="agent_switched",
            actor=from_agent,
            content=f"Routed to {to_agent}: {reasoning}",
            outcome=to_agent,
            user_id=user_id,
        )

    async def record_data_extraction(
        self, thread_id: str, agent_name: str, extracted_data: dict,
        user_id: Optional[str] = None,
    ) -> str:
        return await self.record_event(
            thread_id=thread_id,
            episode_type="EXTRACTION",
            action="data_extracted",
            actor=agent_name,
            data_snapshot=extracted_data,
            user_id=user_id,
        )

    async def record_search(
        self, thread_id: str, criteria: dict, result_count: int = 0,
        user_id: Optional[str] = None,
    ) -> str:
        return await self.record_event(
            thread_id=thread_id,
            episode_type="SEARCH",
            action="search_performed",
            actor="rent",
            data_snapshot=criteria,
            outcome=f"{result_count} results found",
            user_id=user_id,
        )

    async def record_booking(
        self, thread_id: str, booking_data: dict,
        user_id: Optional[str] = None,
    ) -> str:
        return await self.record_event(
            thread_id=thread_id,
            episode_type="BOOKING",
            action="booking_created",
            actor="calendar",
            data_snapshot=booking_data,
            outcome="booking_pending",
            user_id=user_id,
        )

    # ── Read ───────────────────────────────────────────────────────────

    async def get_thread_episodes(
        self, thread_id: str, limit: int = 50,
    ) -> List[dict]:
        """Get all episodes for a thread, most recent first."""
        async with get_session() as session:
            stmt = (
                select(EpisodicMemoryRecord)
                .where(EpisodicMemoryRecord.thread_id == thread_id)
                .order_by(desc(EpisodicMemoryRecord.timestamp))
                .limit(limit)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            return [
                {
                    "episode_type": r.episode_type,
                    "actor": r.actor,
                    "action": r.action,
                    "content": r.content,
                    "outcome": r.outcome,
                    "data_snapshot": json.loads(r.data_snapshot) if r.data_snapshot else None,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in reversed(records)  # Chronological order
            ]

    async def get_user_history(
        self, user_id: str, limit: int = 20,
    ) -> List[dict]:
        """Get recent episodes across ALL threads for a user (cross-session memory)."""
        async with get_session() as session:
            stmt = (
                select(EpisodicMemoryRecord)
                .where(EpisodicMemoryRecord.user_id == user_id)
                .order_by(desc(EpisodicMemoryRecord.timestamp))
                .limit(limit)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            return [
                {
                    "thread_id": r.thread_id,
                    "episode_type": r.episode_type,
                    "action": r.action,
                    "content": r.content,
                    "outcome": r.outcome,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in reversed(records)
            ]

    async def get_episodes_by_type(
        self, thread_id: str, episode_type: str,
    ) -> List[dict]:
        """Get episodes filtered by type (e.g., only EXTRACTION or HANDOFF)."""
        async with get_session() as session:
            stmt = (
                select(EpisodicMemoryRecord)
                .where(and_(
                    EpisodicMemoryRecord.thread_id == thread_id,
                    EpisodicMemoryRecord.episode_type == episode_type,
                ))
                .order_by(EpisodicMemoryRecord.timestamp)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            return [
                {
                    "actor": r.actor,
                    "action": r.action,
                    "content": r.content,
                    "outcome": r.outcome,
                    "data_snapshot": json.loads(r.data_snapshot) if r.data_snapshot else None,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in records
            ]

    # ── Format for LLM Context ────────────────────────────────────────

    async def format_for_context(
        self, thread_id: str, limit: int = 10,
    ) -> str:
        """Format recent episodes as readable string for LLM context."""
        episodes = await self.get_thread_episodes(thread_id, limit=limit)

        if not episodes:
            return ""

        lines = ["CONVERSATION HISTORY (Episodic Memory):"]
        for ep in episodes:
            actor = ep.get("actor", "system")
            action = ep.get("action", "")
            content = ep.get("content", "")
            ts = ep.get("timestamp", "")[:19]  # Trim microseconds

            if action == "user_message":
                lines.append(f"  [{ts}] User: {content[:200]}")
            elif action == "agent_response":
                lines.append(f"  [{ts}] {actor.capitalize()} Agent: {content[:200]}")
            elif action == "agent_switched":
                lines.append(f"  [{ts}] → Routed to {ep.get('outcome', '?')}")
            elif action == "data_extracted":
                snapshot = ep.get("data_snapshot", {})
                lines.append(f"  [{ts}] 📋 Extracted: {snapshot}")
            else:
                lines.append(f"  [{ts}] {action}: {content[:100] if content else ''}")

        return "\n".join(lines)
