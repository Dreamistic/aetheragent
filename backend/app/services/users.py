from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models import User, UserSettings


def ensure_user_settings(db: Session, user: User) -> UserSettings:
    if user.settings:
        return user.settings
    app_settings = get_settings()
    settings = UserSettings(
        user_id=user.id,
        locale=app_settings.default_locale,
        theme=app_settings.default_theme,
        context_auto_switch_enabled=app_settings.context_auto_switch_enabled,
        session_timeout_minutes=app_settings.session_timeout_minutes,
        carried_over_message_count=app_settings.carried_over_message_count,
        carried_over_expire_threshold=app_settings.carried_over_expire_threshold,
        auto_summary_enabled=app_settings.auto_summary_enabled,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def find_user_by_login(db: Session, username_or_email: str) -> User | None:
    login = username_or_email.strip()
    stmt = select(User).where(or_(User.username == login, User.email == login.lower()))
    return db.execute(stmt).scalar_one_or_none()

