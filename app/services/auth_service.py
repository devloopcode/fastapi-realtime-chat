from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.user_repo import UserRepository
from app.schemas.token import TokenPair
from app.core.config import settings


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)
        self._tokens = RefreshTokenRepository(session)

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> User:
        if await self._users.get_by_username(username):
            raise ConflictError(f"Username '{username}' is already taken")
        if await self._users.get_by_email(email):
            raise ConflictError(f"Email '{email}' is already registered")

        return await self._users.create(
            username=username.lower(),
            email=email.lower(),
            hashed_password=hash_password(password),
            display_name=display_name or username,
        )

    async def login(self, username: str, password: str) -> TokenPair:
        user = await self._users.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid username or password")
        if not user.is_active:
            raise AuthenticationError("Account is disabled")

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        await self._tokens.create_token(user.id, refresh_token, expires_at)

        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    async def refresh(self, refresh_token: str) -> TokenPair:
        from jose import JWTError

        try:
            user_id_str = decode_refresh_token(refresh_token)
        except JWTError as exc:
            raise AuthenticationError("Invalid or expired refresh token") from exc

        db_token = await self._tokens.get_valid_token(refresh_token)
        if not db_token:
            raise AuthenticationError("Refresh token revoked or expired")

        # Rotate: revoke old, issue new
        await self._tokens.revoke_token(refresh_token)

        user_id = uuid.UUID(user_id_str)
        new_access = create_access_token(user_id)
        new_refresh = create_refresh_token(user_id)

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        await self._tokens.create_token(user_id, new_refresh, expires_at)

        return TokenPair(access_token=new_access, refresh_token=new_refresh)
