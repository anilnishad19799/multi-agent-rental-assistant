"""Re-export all SQLAlchemy models so every model class is registered with the
mapper before any query is executed.  Importing ``backend.models`` (or any
sub-module) will trigger this ``__init__`` and guarantee that cross-model
string references (e.g. ``relationship("User")``) can be resolved.
"""

from backend.models.base import Base, engine, AsyncSessionLocal, get_session, init_db  # noqa: F401

# ── Domain models (order matters: referenced models first) ────────────────
from backend.models.user import User, UserPreference  # noqa: F401
from backend.models.property import (  # noqa: F401
    Property, PropertyConfig, PropertyAmenity, PropertyImage, LandlordPreference,
)
from backend.models.conversation import (  # noqa: F401
    Conversation, Message, ConversationMemory, UserExtractedInfoLog,
)
from backend.models.booking import (  # noqa: F401
    SearchRequest, SearchResult, ShortlistedProperty, Booking,
    RealEstateAgent, AgentAvailability,
)
from backend.models.memory import (  # noqa: F401
    SemanticMemoryRecord, EpisodicMemoryRecord, ProceduralMemoryRecord,
)

__all__ = [
    "Base", "engine", "AsyncSessionLocal", "get_session", "init_db",
    "User", "UserPreference",
    "Property", "PropertyConfig", "PropertyAmenity", "PropertyImage", "LandlordPreference",
    "Conversation", "Message", "ConversationMemory", "UserExtractedInfoLog",
    "SearchRequest", "SearchResult", "ShortlistedProperty", "Booking",
    "RealEstateAgent", "AgentAvailability",
    "SemanticMemoryRecord", "EpisodicMemoryRecord", "ProceduralMemoryRecord",
]
