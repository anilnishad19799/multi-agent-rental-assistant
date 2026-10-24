"""Procedural Memory — stores learned patterns and user preferences.

Procedural memory answers: "HOW should we interact with this user?"

Examples:
  - PREFERENCE: User is price-sensitive (always asks about budget first)
  - BEHAVIOR:   User prefers short, concise responses
  - SEQUENCE:   User's typical flow is search → info → booking
  - RULE:       If user mentions "Hadapsar", they mean Pune
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

from sqlalchemy import select, and_
from backend.models.base import get_session
from backend.models import ProceduralMemoryRecord

logger = logging.getLogger(__name__)


class ProceduralMemory:
    """Stores and retrieves learned patterns and behavioral rules."""

    # ── Write ──────────────────────────────────────────────────────────

    async def record_pattern(
        self,
        pattern_type: str,
        pattern_key: str,
        pattern_value: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Record or reinforce a pattern. Increments frequency if pattern exists."""
        async with get_session() as session:
            conditions = [
                ProceduralMemoryRecord.pattern_type == pattern_type,
                ProceduralMemoryRecord.pattern_key == pattern_key,
            ]
            if user_id:
                conditions.append(ProceduralMemoryRecord.user_id == user_id)

            stmt = select(ProceduralMemoryRecord).where(and_(*conditions))
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.frequency += 1
                existing.pattern_value = pattern_value
                existing.last_observed_at = datetime.now(timezone.utc)
            else:
                record = ProceduralMemoryRecord(
                    user_id=user_id,
                    pattern_type=pattern_type,
                    pattern_key=pattern_key,
                    pattern_value=pattern_value,
                    frequency=1,
                )
                session.add(record)

            await session.commit()

    async def record_preference(
        self, key: str, value: str, user_id: Optional[str] = None,
    ) -> None:
        """Shorthand for recording a user preference."""
        await self.record_pattern("PREFERENCE", key, value, user_id)

    async def record_behavior(
        self, key: str, value: str, user_id: Optional[str] = None,
    ) -> None:
        """Shorthand for recording a behavioral pattern."""
        await self.record_pattern("BEHAVIOR", key, value, user_id)

    async def record_agent_sequence(
        self, sequence: List[str], user_id: Optional[str] = None,
    ) -> None:
        """Record the agent sequence for this conversation as a flow pattern."""
        flow = " → ".join(sequence)
        await self.record_pattern("SEQUENCE", "agent_flow", flow, user_id)

    # ── Read ───────────────────────────────────────────────────────────

    async def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[dict]:
        """Get patterns, optionally filtered by type and/or user."""
        async with get_session() as session:
            conditions = []
            if pattern_type:
                conditions.append(
                    ProceduralMemoryRecord.pattern_type == pattern_type
                )
            if user_id:
                conditions.append(
                    ProceduralMemoryRecord.user_id == user_id
                )

            stmt = select(ProceduralMemoryRecord)
            if conditions:
                stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(ProceduralMemoryRecord.frequency.desc())

            result = await session.execute(stmt)
            records = result.scalars().all()

            return [
                {
                    "type": r.pattern_type,
                    "key": r.pattern_key,
                    "value": r.pattern_value,
                    "frequency": r.frequency,
                    "last_observed": (
                        r.last_observed_at.isoformat()
                        if r.last_observed_at else None
                    ),
                }
                for r in records
            ]

    async def get_user_preferences(self, user_id: str) -> Dict[str, str]:
        """Get all preferences for a user as a key-value dict."""
        patterns = await self.get_patterns("PREFERENCE", user_id)
        return {p["key"]: p["value"] for p in patterns}

    # ── Format for LLM Context ────────────────────────────────────────

    async def format_for_context(
        self, user_id: Optional[str] = None,
    ) -> str:
        """Format learned patterns as readable string for LLM context."""
        patterns = await self.get_patterns(user_id=user_id)

        if not patterns:
            return ""

        lines = ["LEARNED PATTERNS (Procedural Memory):"]
        for p in patterns:
            freq = f" (observed {p['frequency']}x)" if p["frequency"] > 1 else ""
            lines.append(f"  [{p['type']}] {p['key']}: {p['value']}{freq}")

        return "\n".join(lines)
