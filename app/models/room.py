from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RoomType(str, enum.Enum):
    public = "public"
    private = "private"
    direct = "direct"  # 1-to-1 DM


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    room_type: Mapped[RoomType] = mapped_column(
        Enum(RoomType, name="roomtype"), default=RoomType.public, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    members: Mapped[list[RoomMember]] = relationship(
        "RoomMember", back_populates="room", lazy="noload", cascade="all, delete-orphan"
    )
    messages: Mapped[list[Message]] = relationship(  # type: ignore[name-defined]
        "Message", back_populates="room", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<ChatRoom {self.name}>"


class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_member"),
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    room: Mapped[ChatRoom] = relationship("ChatRoom", back_populates="members")
    user: Mapped[User] = relationship("User", back_populates="room_memberships")  # type: ignore[name-defined]
