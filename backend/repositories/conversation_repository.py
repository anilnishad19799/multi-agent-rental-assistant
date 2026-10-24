"""Conversation repository — messages, memory, conversation management."""
import logging
from typing import List, Optional, Dict
from sqlalchemy import select, and_
from backend.models.base import get_session
from backend.models import (
    Conversation, Message, ConversationMemory, UserExtractedInfoLog,
)
from backend.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ConversationRepository(BaseRepository[Conversation]):

    def __init__(self):
        super().__init__(Conversation)

    async def get_or_create_conversation(self, session_id: str) -> Conversation:
        async with get_session() as session:
            stmt = select(Conversation).where(Conversation.session_id == session_id)
            result = await session.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                return conv

            conv = Conversation(session_id=session_id)
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            logger.info(f"Created conversation for session {session_id}")
            return conv

    async def add_message(
        self, conversation_id: str, sender_type: str,
        content: str, agent_type: Optional[str] = None,
    ) -> Message:
        async with get_session() as session:
            msg = Message(
                conversation_id=conversation_id,
                sender_type=sender_type,
                agent_type=agent_type,
                content=content,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            return msg

    async def get_conversation_history(
        self, session_id: str, limit: int = 50
    ) -> List[Message]:
        async with get_session() as session:
            # First get conversation by session_id
            conv_stmt = select(Conversation).where(Conversation.session_id == session_id)
            conv_result = await session.execute(conv_stmt)
            conv = conv_result.scalar_one_or_none()
            if not conv:
                return []

            stmt = (
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            messages = list(result.scalars().all())
            messages.reverse()  # oldest first
            return messages

    async def set_memory(self, conversation_id: str, key: str, value: str) -> None:
        async with get_session() as session:
            stmt = select(ConversationMemory).where(
                and_(
                    ConversationMemory.conversation_id == conversation_id,
                    ConversationMemory.key == key,
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.value = value
            else:
                entry = ConversationMemory(
                    conversation_id=conversation_id,
                    key=key,
                    value=value,
                )
                session.add(entry)

            await session.commit()

    async def get_memory(self, conversation_id: str) -> Dict[str, str]:
        async with get_session() as session:
            stmt = select(ConversationMemory).where(
                ConversationMemory.conversation_id == conversation_id
            )
            result = await session.execute(stmt)
            entries = result.scalars().all()
            return {e.key: e.value for e in entries}

    async def get_memory_value(self, conversation_id: str, key: str) -> Optional[str]:
        async with get_session() as session:
            stmt = select(ConversationMemory).where(
                and_(
                    ConversationMemory.conversation_id == conversation_id,
                    ConversationMemory.key == key,
                )
            )
            result = await session.execute(stmt)
            entry = result.scalar_one_or_none()
            return entry.value if entry else None

    async def log_extracted_info(
        self, user_id: Optional[str], field_name: str,
        field_value: str, source_agent: str, confidence: float = 1.0,
    ) -> UserExtractedInfoLog:
        async with get_session() as session:
            log = UserExtractedInfoLog(
                user_id=user_id,
                field_name=field_name,
                field_value=field_value,
                source_agent=source_agent,
                confidence_score=confidence,
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            return log

    async def update_current_agent(self, session_id: str, agent_name: str) -> None:
        async with get_session() as session:
            stmt = select(Conversation).where(Conversation.session_id == session_id)
            result = await session.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                conv.current_agent = agent_name
                await session.commit()
