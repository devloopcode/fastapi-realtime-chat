from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    bad_request_exception,
    conflict_exception,
    forbidden_exception,
    not_found_exception,
)
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.room import ChatRoom
from app.models.user import User
from app.repositories.room_repo import RoomRepository
from app.schemas.room import RoomCreate, RoomDetail, RoomResponse
from app.schemas.user import UserPublic
from app.services.room_service import RoomService

router = APIRouter(prefix="/rooms", tags=["Rooms"])


def _room_response(room: ChatRoom, count: int) -> RoomResponse:
    return RoomResponse.model_validate(room).model_copy(update={"member_count": count})


@router.post(
    "",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat room",
)
async def create_room(
    data: RoomCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoomResponse:
    svc = RoomService(db)
    room = await svc.create_room(data, current_user)
    count = await svc.member_count(room.id)
    await db.commit()
    await db.refresh(room)
    return _room_response(room, count)


@router.get(
    "",
    response_model=list[RoomResponse],
    summary="List all public rooms (paginated)",
)
async def list_rooms(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RoomResponse]:
    svc = RoomService(db)
    rooms = await svc.get_public_rooms(limit=limit, offset=offset)
    result = []
    for r in rooms:
        count = await svc.member_count(r.id)
        result.append(_room_response(r, count))
    return result


@router.get(
    "/me",
    response_model=list[RoomResponse],
    summary="List rooms the current user belongs to",
)
async def my_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RoomResponse]:
    svc = RoomService(db)
    rooms = await svc.get_user_rooms(current_user.id)
    result = []
    for r in rooms:
        count = await svc.member_count(r.id)
        result.append(_room_response(r, count))
    return result


@router.get(
    "/{room_id}",
    response_model=RoomDetail,
    summary="Get room details including member list",
)
async def get_room(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoomDetail:
    svc = RoomService(db)
    try:
        room = await svc.get_room_detail(room_id, current_user.id)
    except NotFoundError:
        raise not_found_exception("Room")
    except AuthorizationError as exc:
        raise forbidden_exception(exc.message)

    members = [
        UserPublic.model_validate(m.user)
        for m in room.members
        if m.user is not None
    ]
    base = RoomResponse.model_validate(room).model_copy(update={"member_count": len(members)})
    return RoomDetail(**base.model_dump(), members=members)


@router.post(
    "/{room_id}/join",
    response_model=RoomResponse,
    summary="Join a public room",
)
async def join_room(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoomResponse:
    svc = RoomService(db)
    try:
        await svc.join_room(room_id, current_user)
    except NotFoundError:
        raise not_found_exception("Room")
    except (ConflictError, AuthorizationError) as exc:
        raise conflict_exception(exc.message)
    await db.commit()
    room = await RoomRepository(db).get_by_id(room_id)
    count = await svc.member_count(room_id)
    return _room_response(room, count)


@router.post(
    "/{room_id}/leave",
    summary="Leave a room",
)
async def leave_room(
    room_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = RoomService(db)
    try:
        await svc.leave_room(room_id, current_user.id)
    except NotFoundError:
        raise not_found_exception("Room")
    except ConflictError as exc:
        raise bad_request_exception(exc.message)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
