from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError, bad_request_exception, conflict_exception, credentials_exception
from app.dependencies.database import get_db
from app.schemas.token import AccessToken, RefreshRequest, TokenPair
from app.schemas.user import UserRegister, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    svc = AuthService(db)
    try:
        user = await svc.register(
            username=data.username,
            email=data.email,
            password=data.password,
            display_name=data.display_name,
        )
    except ConflictError as exc:
        raise conflict_exception(exc.message)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Login and receive access + refresh tokens",
)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    svc = AuthService(db)
    try:
        tokens = await svc.login(form.username, form.password)
    except AuthenticationError as exc:
        raise credentials_exception()
    await db.commit()
    return tokens


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Exchange a refresh token for a new token pair (rotation)",
)
async def refresh(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    svc = AuthService(db)
    try:
        tokens = await svc.refresh(data.refresh_token)
    except AuthenticationError as exc:
        raise bad_request_exception(exc.message)
    await db.commit()
    return tokens
