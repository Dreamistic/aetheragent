from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=6, max_length=256)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("email format is invalid")
        return value.lower()


class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class ProfileUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=80)
    display_name: str | None = Field(default=None, max_length=120)
    avatar_data: str | None = Field(default=None, max_length=2_000_000)

    @field_validator("avatar_data")
    @classmethod
    def validate_avatar_data(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not value.startswith("data:image/"):
            raise ValueError("avatar must be a data:image URL")
        return value


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict
