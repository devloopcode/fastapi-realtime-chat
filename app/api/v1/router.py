from fastapi import APIRouter

from app.api.v1.endpoints import auth, messages, notifications, rooms, upload, users

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(rooms.router)
api_router.include_router(messages.router)
api_router.include_router(notifications.router)
api_router.include_router(upload.router)
