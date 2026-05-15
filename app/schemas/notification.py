from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipient_id: uuid.UUID
    actor_id: uuid.UUID | None
    notification_type: NotificationType
    content: str
    room_id: uuid.UUID | None
    message_id: uuid.UUID | None
    is_read: bool
    created_at: datetime


class UnreadCount(BaseModel):
    count: int
