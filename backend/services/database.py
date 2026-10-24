"""Database service — wraps repositories with business logic."""
import logging
from backend.repositories.user_repository import UserRepository
from backend.repositories.property_repository import PropertyRepository
from backend.repositories.booking_repository import BookingRepository
from backend.repositories.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


class DatabaseService:
    """High-level database access wrapping repository pattern."""

    def __init__(self):
        self.users = UserRepository()
        self.properties = PropertyRepository()
        self.bookings = BookingRepository()
        self.conversations = ConversationRepository()


# Singleton
_db_service = None


def get_db_service() -> DatabaseService:
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
