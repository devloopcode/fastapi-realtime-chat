"""
Import all SQLAlchemy models so that Base.metadata is fully populated.

This module must be imported before calling `Base.metadata.create_all()`
or before Alembic's autogenerate runs. It is NOT part of the application
import chain — it exists solely to avoid circular imports while still
letting Alembic discover all tables.
"""
# ruff: noqa: F401
from app.models.user import User
from app.models.room import ChatRoom, RoomMember
from app.models.message import Message, MessageReadReceipt
from app.models.notification import Notification
from app.models.refresh_token import RefreshToken
