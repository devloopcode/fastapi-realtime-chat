from __future__ import annotations

from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Valid refresh token")


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
