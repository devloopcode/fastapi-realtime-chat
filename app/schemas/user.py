from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, examples=["alice"])
    email: EmailStr = Field(..., examples=["alice@example.com"])
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(None, max_length=100)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric (underscores and hyphens allowed)")
        return v.lower()


class UserLogin(BaseModel):
    username: str = Field(..., examples=["alice"])
    password: str = Field(..., examples=["secret123"])


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: EmailStr
    display_name: str | None
    avatar_url: str | None
    role: UserRole
    is_active: bool
    last_seen: datetime | None
    created_at: datetime


class UserPublic(BaseModel):
    """Minimal public profile — safe to expose to other users."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str | None
    avatar_url: str | None
    last_seen: datetime | None


class OnlineUser(BaseModel):
    user_id: str
    username: str
    status: str = "online"
