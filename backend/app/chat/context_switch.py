from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models import ChatSession, User, UserSettings
from backend.app.services.sessions import create_session


def should_switch_context(settings: UserSettings, session: ChatSession) -> tuple[bool, str]:
    if not settings.context_auto_switch_enabled:
        return False, "disabled"
    message_count = len(session.messages or [])
    min_messages = get_settings().auto_switch_min_messages
    if message_count < min_messages:
        return False, "below_threshold"
    if session.summary and message_count < min_messages * 2:
        return False, "already_summarized"
    return True, "context_length"


def perform_context_switch(db: Session, user: User) -> ChatSession:
    return create_session(db, user, auto_summarize=True)

