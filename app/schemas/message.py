from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    content: str | None = Field(None, max_length=4000)
    image_url: str | None = Field(None, description="URL of an uploaded image")

    def model_post_init(self, __context: object) -> None:
        if not self.content and not self.image_url:
            raise ValueError("Message must have content or an image")


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    sender_id: uuid.UUID | None
    sender_username: str | None = None
    sender_display_name: str | None = None
    sender_avatar_url: str | None = None
    content: str | None
    image_url: str | None
    is_deleted: bool
    created_at: datetime
    read_by: list[str] = []


class MarkReadRequest(BaseModel):
    message_ids: list[uuid.UUID] = Field(..., min_length=1)


class PaginatedMessages(BaseModel):
    items: list[MessageResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
