from __future__ import annotations

from pydantic import BaseModel, Field


class ImageData(BaseModel):
    data: str
    mime_type: str


class ChatStreamRequest(BaseModel):
    message: str = Field(default="")
    session_id: str | None = None
    route: str | None = None
    images: list[ImageData] = Field(default_factory=list)


class NewSessionRequest(BaseModel):
    auto_summarize: bool = True


class FavoriteRequest(BaseModel):
    is_favorite: bool

