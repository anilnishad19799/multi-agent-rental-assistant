"""Semantic Memory — stores and retrieves FACTS about entities.

Semantic memory answers: "What do we KNOW about this user/topic?"

Examples:
  - User's name is Rahul
  - User's age is 25
  - User wants to rent in Hadapsar
  - User's budget is ₹8,000
  - User prefers 2-sharing PG
"""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

from sqlalchemy import select, and_
from backend.models.base import get_session
from backend.models import SemanticMemoryRecord

logger = logging.getLogger(__name__)


class SemanticMemory:
    """Stores and retrieves factual knowledge (entity-fact pairs) in the database."""

    # ── Write ──────────────────────────────────────────────────────────

    async def store_fact(
        self,
        entity_type: str,
        fact_key: str,
        fact_value: str,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        source_agent: Optional[str] = None,
        confidence: float = 1.0,
    ) -> None:
        """Store or update a single fact. Upserts by (user_id, entity_type, fact_key)."""
        async with get_session() as session:
            # Try to find existing fact to update
            conditions = [
                SemanticMemoryRecord.entity_type == entity_type,
                SemanticMemoryRecord.fact_key == fact_key,
            ]
            if user_id:
                conditions.append(SemanticMemoryRecord.user_id == user_id)
            elif thread_id:
                conditions.append(SemanticMemoryRecord.thread_id == thread_id)

            stmt = select(SemanticMemoryRecord).where(and_(*conditions))
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.fact_value = fact_value
                existing.confidence = confidence
                existing.source_agent = source_agent
                existing.updated_at = datetime.now(timezone.utc)
            else:
                record = SemanticMemoryRecord(
                    user_id=user_id,
                    thread_id=thread_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    fact_key=fact_key,
                    fact_value=fact_value,
                    confidence=confidence,
                    source_agent=source_agent,
                )
                session.add(record)

            await session.commit()

    async def store_facts_batch(
        self,
        facts: Dict[str, str],
        entity_type: str,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        source_agent: Optional[str] = None,
    ) -> None:
        """Store multiple facts at once. Skips None values."""
        for key, value in facts.items():
            if value is not None and key != "missing_fields":
                await self.store_fact(
                    entity_type=entity_type,
                    fact_key=key,
                    fact_value=str(value),
                    thread_id=thread_id,
                    user_id=user_id,
                    source_agent=source_agent,
                )

    # ── Read ───────────────────────────────────────────────────────────

    async def get_facts_by_entity(
        self,
        entity_type: str,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Retrieve all facts for a given entity type, keyed by fact_key."""
        async with get_session() as session:
            conditions = [SemanticMemoryRecord.entity_type == entity_type]
            if user_id:
                conditions.append(SemanticMemoryRecord.user_id == user_id)
            elif thread_id:
                conditions.append(SemanticMemoryRecord.thread_id == thread_id)

            stmt = select(SemanticMemoryRecord).where(and_(*conditions))
            result = await session.execute(stmt)
            records = result.scalars().all()

            return {r.fact_key: r.fact_value for r in records}

    async def get_all_user_facts(
        self, user_id: str
    ) -> Dict[str, Dict[str, str]]:
        """Get ALL facts for a user, grouped by entity_type."""
        async with get_session() as session:
            stmt = select(SemanticMemoryRecord).where(
                SemanticMemoryRecord.user_id == user_id
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            grouped: Dict[str, Dict[str, str]] = {}
            for r in records:
                grouped.setdefault(r.entity_type, {})[r.fact_key] = r.fact_value
            return grouped

    async def get_fact(
        self,
        entity_type: str,
        fact_key: str,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> Optional[str]:
        """Get a single fact value."""
        async with get_session() as session:
            conditions = [
                SemanticMemoryRecord.entity_type == entity_type,
                SemanticMemoryRecord.fact_key == fact_key,
            ]
            if user_id:
                conditions.append(SemanticMemoryRecord.user_id == user_id)
            elif thread_id:
                conditions.append(SemanticMemoryRecord.thread_id == thread_id)

            stmt = select(SemanticMemoryRecord).where(and_(*conditions))
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            return record.fact_value if record else None

    # ── Format for LLM Context ────────────────────────────────────────

    async def format_for_context(
        self,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> str:
        """Format all known facts as a readable string for LLM context."""
        all_facts: Dict[str, Dict[str, str]] = {}

        if user_id:
            all_facts = await self.get_all_user_facts(user_id)
        elif thread_id:
            for entity_type in ("USER", "SEARCH", "PREF"):
                facts = await self.get_facts_by_entity(
                    entity_type, thread_id=thread_id,
                )
                if facts:
                    all_facts[entity_type] = facts

        if not all_facts:
            return ""

        lines = ["KNOWN FACTS (Semantic Memory):"]
        for entity_type, facts in all_facts.items():
            lines.append(f"  [{entity_type}]")
            for key, value in facts.items():
                lines.append(f"    - {key}: {value}")

        return "\n".join(lines)
