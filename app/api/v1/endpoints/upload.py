from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel

from app.core.exceptions import ValidationError, bad_request_exception
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.upload_service import save_upload

router = APIRouter(prefix="/upload", tags=["Upload"])


class UploadResponse(BaseModel):
    url: str
    filename: str


@router.post(
    "/image",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image and receive its URL for use in messages",
)
async def upload_image(
    file: UploadFile = File(..., description="Image file (JPEG, PNG, GIF, WebP)"),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    try:
        url = await save_upload(file)
    except ValidationError as exc:
        raise bad_request_exception(exc.message)
    filename = url.split("/")[-1]
    return UploadResponse(url=url, filename=filename)
