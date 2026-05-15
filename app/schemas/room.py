from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.room import RoomType
from app.schemas.user import UserPublic


class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["general"])
    description: str | None = Field(None, max_length=500)
    room_type: RoomType = RoomType.public


class RoomUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class RoomMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    user_id: uuid.UUID
    is_admin: bool
    created_at: datetime


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    room_type: RoomType
    is_active: bool
    owner_id: uuid.UUID | None
    created_at: datetime
    member_count: int = 0


class RoomDetail(RoomResponse):
    members: list[UserPublic] = []
