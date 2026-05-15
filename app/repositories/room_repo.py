from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.room import ChatRoom, RoomMember, RoomType
from app.models.user import User
from app.repositories.base import BaseRepository


class RoomRepository(BaseRepository[ChatRoom]):
    model = ChatRoom

    async def get_public_rooms(self, limit: int = 50, offset: int = 0) -> list[ChatRoom]:
        result = await self.session.execute(
            select(ChatRoom)
            .where(ChatRoom.room_type == RoomType.public, ChatRoom.is_active == True)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_rooms(self, user_id: uuid.UUID) -> list[ChatRoom]:
        result = await self.session.execute(
            select(ChatRoom)
            .join(RoomMember, RoomMember.room_id == ChatRoom.id)
            .where(RoomMember.user_id == user_id, ChatRoom.is_active == True)
        )
        return list(result.scalars().all())

    async def get_with_members(self, room_id: uuid.UUID) -> ChatRoom | None:
        result = await self.session.execute(
            select(ChatRoom)
            .where(ChatRoom.id == room_id)
            .options(selectinload(ChatRoom.members).selectinload(RoomMember.user))
        )
        return result.scalar_one_or_none()

    async def get_member(self, room_id: uuid.UUID, user_id: uuid.UUID) -> RoomMember | None:
        result = await self.session.execute(
            select(RoomMember).where(
                RoomMember.room_id == room_id, RoomMember.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def add_member(self, room_id: uuid.UUID, user_id: uuid.UUID, is_admin: bool = False) -> RoomMember:
        member = RoomMember(room_id=room_id, user_id=user_id, is_admin=is_admin)
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def remove_member(self, room_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(RoomMember).where(
                RoomMember.room_id == room_id, RoomMember.user_id == user_id
            )
        )
        await self.session.flush()

    async def member_count(self, room_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(RoomMember).where(RoomMember.room_id == room_id)
        )
        return result.scalar_one()

    async def is_member(self, room_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return await self.get_member(room_id, user_id) is not None
