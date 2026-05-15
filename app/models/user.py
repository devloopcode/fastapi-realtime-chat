from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"), default=UserRole.user, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    messages: Mapped[list[Message]] = relationship(  # type: ignore[name-defined]
        "Message", back_populates="sender", lazy="noload"
    )
    room_memberships: Mapped[list[RoomMember]] = relationship(  # type: ignore[name-defined]
        "RoomMember", back_populates="user", lazy="noload"
    )
    notifications: Mapped[list[Notification]] = relationship(  # type: ignore[name-defined]
        "Notification",
        back_populates="recipient",
        lazy="noload",
        foreign_keys="[Notification.recipient_id]",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(  # type: ignore[name-defined]
        "RefreshToken", back_populates="user", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"
