"""Conversation repository — messages, memory, conversation management."""
import logging
from typing import List, Optional, Dict, Any
from uuid import uuid4
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

    async def get_or_create_conversation(self, session_id: str, user_id: Optional[str] = None) -> Conversation:
        async with get_session() as session:
            stmt = select(Conversation).where(Conversation.session_id == session_id)
            result = await session.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                # If this session belongs to another user, DO NOT allow sharing/cross-contamination!
                if conv.user_id and user_id and conv.user_id != user_id:
                    logger.warning(
                        f"Session {session_id} belongs to user {conv.user_id}, but requested by {user_id}. Creating new isolated conversation."
                    )
                    new_session_id = str(uuid4())
                    new_conv = Conversation(session_id=new_session_id, user_id=user_id)
                    session.add(new_conv)
                    await session.commit()
                    await session.refresh(new_conv)
                    return new_conv

                if user_id and not conv.user_id:
                    conv.user_id = user_id
                    await session.commit()
                    await session.refresh(conv)
                return conv

            conv = Conversation(session_id=session_id, user_id=user_id)
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            logger.info(f"Created conversation for session {session_id} with user {user_id}")
            return conv

    async def get_latest_conversation_for_user(self, user_id: str) -> Optional[Conversation]:
        """Fetch the most recent conversation owned by a specific user."""
        if not user_id:
            return None
        async with get_session() as session:
            stmt = (
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_user_conversation_messages(self, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """Fetch all messages from the latest conversation of a specific user."""
        conv = await self.get_latest_conversation_for_user(user_id)
        if not conv:
            return {"session_id": None, "messages": []}
        messages = await self.get_conversation_history(conv.session_id, limit=limit)
        return {
            "session_id": conv.session_id,
            "messages": [
                {
                    "id": m.id,
                    "sender": m.sender_type,
                    "agent": m.agent_type,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ]
        }

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
