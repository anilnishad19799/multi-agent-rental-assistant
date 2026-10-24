"""SQLAlchemy models for long-term memory: Semantic, Episodic, Procedural."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from backend.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class SemanticMemoryRecord(Base):
    """Semantic Memory — stores facts and knowledge about entities.

    Examples:
      entity_type=USER,  fact_key=name,        fact_value=Rahul
      entity_type=USER,  fact_key=age,          fact_value=25
      entity_type=SEARCH, fact_key=city,        fact_value=Pune
      entity_type=PREF,  fact_key=sharing_type, fact_value=2
    """
    __tablename__ = "semantic_memory"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    thread_id = Column(String, nullable=True, index=True)
    entity_type = Column(String, nullable=False)   # USER, SEARCH, PREF, PROPERTY
    entity_id = Column(String, nullable=True)      # Optional entity reference
    fact_key = Column(String, nullable=False)
    fact_value = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    source_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class EpisodicMemoryRecord(Base):
    """Episodic Memory — stores conversation episodes and events.

    Each user turn or significant event in a conversation is an episode.
    Allows the system to remember WHAT happened and WHEN.
    """
    __tablename__ = "episodic_memory"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    thread_id = Column(String, nullable=False, index=True)
    episode_type = Column(String, nullable=False)  # TURN, SEARCH, BOOKING, EXTRACTION, HANDOFF
    actor = Column(String, nullable=True)          # user / agent name
    action = Column(String, nullable=False)        # user_message, agent_response, search_performed, data_extracted, agent_switched
    content = Column(Text, nullable=True)          # The actual content (message text, search params, etc.)
    outcome = Column(String, nullable=True)        # Result of the action
    data_snapshot = Column(Text, nullable=True)    # JSON: data state at this point
    timestamp = Column(DateTime, default=_utcnow)


class ProceduralMemoryRecord(Base):
    """Procedural Memory — stores learned patterns and user preferences.

    Examples:
      pattern_type=PREFERENCE, pattern_key=budget_sensitivity, pattern_value=high (always asks about price)
      pattern_type=BEHAVIOR,   pattern_key=detail_level,       pattern_value=verbose (prefers detailed listings)
      pattern_type=SEQUENCE,   pattern_key=typical_flow,       pattern_value=search→info→book
    """
    __tablename__ = "procedural_memory"

    id = Column(String, primary_key=True, default=_new_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    pattern_type = Column(String, nullable=False)   # PREFERENCE, BEHAVIOR, SEQUENCE, RULE
    pattern_key = Column(String, nullable=False)
    pattern_value = Column(Text, nullable=False)
    frequency = Column(Integer, default=1)          # How many times observed
    last_observed_at = Column(DateTime, default=_utcnow)
    created_at = Column(DateTime, default=_utcnow)
