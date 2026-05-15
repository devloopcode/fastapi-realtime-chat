from __future__ import annotations

import secrets
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "Real-Time Chat API"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Auth
    secret_key: str = secrets.token_urlsafe(64)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database
    database_url: str = "postgresql+asyncpg://chat:chatpassword@localhost:5432/chatdb"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # File Upload
    max_file_size_mb: int = 10
    upload_dir: str = "uploads/images"
    allowed_image_types: list[str] = ["image/jpeg", "image/png", "image/gif", "image/webp"]

    # Presence & Typing
    presence_ttl_seconds: int = 300
    typing_ttl_seconds: int = 5

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @field_validator("allowed_image_types", mode="before")
    @classmethod
    def parse_image_types(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
