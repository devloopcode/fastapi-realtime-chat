from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models.room import ChatRoom, RoomMember, RoomType
from app.models.user import User
from app.repositories.room_repo import RoomRepository
from app.schemas.room import RoomCreate, RoomResponse


class RoomService:
    def __init__(self, session: AsyncSession) -> None:
        self._rooms = RoomRepository(session)

    async def create_room(self, data: RoomCreate, owner: User) -> ChatRoom:
        room = await self._rooms.create(
            name=data.name,
            description=data.description,
            room_type=data.room_type,
            owner_id=owner.id,
        )
        # Auto-add the creator as an admin member
        await self._rooms.add_member(room.id, owner.id, is_admin=True)
        return room

    async def get_public_rooms(self, limit: int = 50, offset: int = 0) -> list[ChatRoom]:
        return await self._rooms.get_public_rooms(limit=limit, offset=offset)

    async def get_user_rooms(self, user_id: uuid.UUID) -> list[ChatRoom]:
        return await self._rooms.get_user_rooms(user_id)

    async def get_room_detail(self, room_id: uuid.UUID, user_id: uuid.UUID) -> ChatRoom:
        room = await self._rooms.get_with_members(room_id)
        if not room:
            raise NotFoundError("Room")
        if room.room_type != RoomType.public:
            if not await self._rooms.is_member(room_id, user_id):
                raise AuthorizationError("You are not a member of this room")
        return room

    async def join_room(self, room_id: uuid.UUID, user: User) -> RoomMember:
        room = await self._rooms.get_by_id(room_id)
        if not room:
            raise NotFoundError("Room")
        if room.room_type == RoomType.direct:
            raise AuthorizationError("Cannot join a direct message room")
        if await self._rooms.is_member(room_id, user.id):
            raise ConflictError("Already a member of this room")
        return await self._rooms.add_member(room_id, user.id)

    async def leave_room(self, room_id: uuid.UUID, user_id: uuid.UUID) -> None:
        room = await self._rooms.get_by_id(room_id)
        if not room:
            raise NotFoundError("Room")
        if not await self._rooms.is_member(room_id, user_id):
            raise ConflictError("Not a member of this room")
        await self._rooms.remove_member(room_id, user_id)

    async def member_count(self, room_id: uuid.UUID) -> int:
        return await self._rooms.member_count(room_id)

    async def assert_membership(self, room_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Raise AuthorizationError if user is not a room member."""
        if not await self._rooms.is_member(room_id, user_id):
            raise AuthorizationError("You are not a member of this room")
