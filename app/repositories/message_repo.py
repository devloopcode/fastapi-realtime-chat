from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.message import Message, MessageReadReceipt
from app.models.user import User
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def get_room_messages(
        self,
        room_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Message], int]:
        offset = (page - 1) * page_size

        count_result = await self.session.execute(
            select(func.count()).select_from(Message).where(
                Message.room_id == room_id, Message.is_deleted == False
            )
        )
        total = count_result.scalar_one()

        messages_result = await self.session.execute(
            select(Message)
            .where(Message.room_id == room_id, Message.is_deleted == False)
            .options(
                selectinload(Message.sender),
                selectinload(Message.read_receipts),
            )
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        messages = list(messages_result.scalars().all())
        return messages, total

    async def create_with_sender(
        self,
        room_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str | None,
        image_url: str | None,
    ) -> Message:
        msg = Message(room_id=room_id, sender_id=sender_id, content=content, image_url=image_url)
        self.session.add(msg)
        await self.session.flush()
        # Reload with relationships
        result = await self.session.execute(
            select(Message)
            .where(Message.id == msg.id)
            .options(selectinload(Message.sender), selectinload(Message.read_receipts))
        )
        return result.scalar_one()

    async def mark_read(self, message_ids: list[uuid.UUID], user_id: uuid.UUID) -> None:
        """Insert read receipts, ignoring duplicates."""
        existing = await self.session.execute(
            select(MessageReadReceipt.message_id).where(
                MessageReadReceipt.message_id.in_(message_ids),
                MessageReadReceipt.user_id == user_id,
            )
        )
        already_read = {row[0] for row in existing.fetchall()}
        new_ids = [mid for mid in message_ids if mid not in already_read]
        if new_ids:
            await self.session.execute(
                insert(MessageReadReceipt),
                [{"message_id": mid, "user_id": user_id} for mid in new_ids],
            )
            await self.session.flush()

    async def get_unread_count(self, room_id: uuid.UUID, user_id: uuid.UUID) -> int:
        subq = select(MessageReadReceipt.message_id).where(
            MessageReadReceipt.user_id == user_id
        )
        result = await self.session.execute(
            select(func.count()).select_from(Message).where(
                Message.room_id == room_id,
                Message.is_deleted == False,
                Message.sender_id != user_id,
                Message.id.not_in(subq),
            )
        )
        return result.scalar_one()
