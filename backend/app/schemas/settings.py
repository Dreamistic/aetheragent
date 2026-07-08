from __future__ import annotations

from pydantic import BaseModel, Field


class UserSettingsUpdate(BaseModel):
    locale: str | None = Field(default=None, pattern="^[A-Za-z-]+$")
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")
    api_base_url: str | None = None
    context_auto_switch_enabled: bool | None = None
    session_timeout_minutes: int | None = Field(default=None, ge=1, le=1440)
    carried_over_message_count: int | None = Field(default=None, ge=0, le=50)
    carried_over_expire_threshold: int | None = Field(default=None, ge=1, le=200)
    auto_summary_enabled: bool | None = None

