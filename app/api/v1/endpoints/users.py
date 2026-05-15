from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import OnlineUser, UserResponse
from app.services.presence_service import get_online_users

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user's profile",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get(
    "/online",
    response_model=list[OnlineUser],
    summary="Get all currently online users (Redis-backed)",
)
async def get_online(_: User = Depends(get_current_user)) -> list[OnlineUser]:
    users = await get_online_users()
    return [OnlineUser(**u) for u in users]
