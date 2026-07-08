from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import ChatSession, Message, User, UserSettings, utc_now
from backend.app.services.users import ensure_user_settings


def summarize_messages(messages: list[Message], limit: int = 600) -> str:
    if not messages:
        return ""
    parts: list[str] = []
    for message in messages[-8:]:
        content = " ".join((message.content or "").split())
        if not content:
            continue
        parts.append(f"{message.role}: {content[:160]}")
    summary = "\n".join(parts)
    return summary[:limit]


def carried_context_from(session: ChatSession, count: int) -> list[dict]:
    if count <= 0:
        return []
    context = []
    for message in (session.messages or [])[-count:]:
        if message.role in {"user", "assistant"} and message.content:
            context.append(
                {
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                }
            )
    return context


def create_session(db: Session, user: User, auto_summarize: bool = True) -> ChatSession:
    settings = ensure_user_settings(db, user)
    previous_session: ChatSession | None = None
    carried: list[dict] = []
    if settings.current_session_id:
        previous_session = get_session(db, user, settings.current_session_id)
        if previous_session:
            if auto_summarize and settings.auto_summary_enabled and not previous_session.summary:
                previous_session.summary = summarize_messages(previous_session.messages)
            carried = carried_context_from(previous_session, settings.carried_over_message_count)

    session = ChatSession(
        user_id=user.id,
        title="新会话" if settings.locale == "zh-Hans" else ("新會話" if settings.locale == "zh-Hant" else "New chat"),
        previous_session_id=previous_session.id if previous_session else None,
        carried_over_context=carried,
        last_activity_at=utc_now(),
    )
    db.add(session)
    db.flush()
    settings.current_session_id = session.id
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, user: User, session_id: str) -> ChatSession | None:
    stmt = select(ChatSession).where(ChatSession.user_id == user.id, ChatSession.id == session_id)
    return db.execute(stmt).scalar_one_or_none()


def get_or_create_current_session(db: Session, user: User) -> ChatSession:
    settings = ensure_user_settings(db, user)
    if settings.current_session_id:
        session = get_session(db, user, settings.current_session_id)
        if session:
            return session
    return create_session(db, user, auto_summarize=False)


def list_sessions(db: Session, user: User) -> list[ChatSession]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(desc(ChatSession.is_favorite), desc(ChatSession.last_activity_at))
    )
    return list(db.execute(stmt).scalars().all())


def set_current_session(db: Session, user: User, session: ChatSession) -> UserSettings:
    settings = ensure_user_settings(db, user)
    settings.current_session_id = session.id
    db.commit()
    db.refresh(settings)
    return settings


def add_message(
    db: Session,
    user: User,
    session: ChatSession,
    role: str,
    content: str,
    *,
    raw_content: str | None = None,
    route: str | None = None,
    route_detail: str | None = None,
    images: list | None = None,
    meta: dict | None = None,
) -> Message:
    message = Message(
        user_id=user.id,
        session_id=session.id,
        role=role,
        content=content,
        raw_content=raw_content,
        route=route,
        route_detail=route_detail,
        images=images or [],
        meta=meta or {},
    )
    db.add(message)
    session.last_activity_at = utc_now()
    if role == "user" and session.title in {"New chat", "新会话", "新會話"} and content.strip():
        session.title = " ".join(content.split())[:40]
    db.commit()
    db.refresh(message)
    db.refresh(session)
    return message
