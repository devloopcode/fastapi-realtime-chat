from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_ids(self, ids: list[uuid.UUID]) -> list[User]:
        result = await self.session.execute(select(User).where(User.id.in_(ids)))
        return list(result.scalars().all())

    async def update_last_seen(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_seen=datetime.now(timezone.utc))
        )
        await self.session.flush()

    async def update_avatar(self, user_id: uuid.UUID, avatar_url: str) -> User | None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(avatar_url=avatar_url)
        )
        await self.session.flush()
        return await self.get_by_id(user_id)
