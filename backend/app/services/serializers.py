from __future__ import annotations

from backend.app.db.models import CalendarEvent, ChatSession, MemoryItem, Message, Task, User, UserSettings


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "email": user.email,
        "avatar_data": user.avatar_data,
        "email_verified": user.email_verified,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    }


def settings_to_dict(settings: UserSettings) -> dict:
    return {
        "locale": settings.locale,
        "theme": settings.theme,
        "api_base_url": settings.api_base_url,
        "current_session_id": settings.current_session_id,
        "context_auto_switch_enabled": settings.context_auto_switch_enabled,
        "session_timeout_minutes": settings.session_timeout_minutes,
        "carried_over_message_count": settings.carried_over_message_count,
        "carried_over_expire_threshold": settings.carried_over_expire_threshold,
        "auto_summary_enabled": settings.auto_summary_enabled,
    }


def message_to_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "raw_content": message.raw_content,
        "route": message.route,
        "route_detail": message.route_detail,
        "images": message.images or [],
        "meta": message.meta or {},
        "created_at": message.created_at.isoformat(),
    }


def session_to_dict(session: ChatSession, include_messages: bool = False) -> dict:
    data = {
        "session_id": session.id,
        "title": session.title,
        "summary": session.summary,
        "previous_session_id": session.previous_session_id,
        "message_count": len(session.messages or []),
        "preview": _preview(session),
        "is_favorite": session.is_favorite,
        "created_at": session.created_at.isoformat(),
        "last_activity_at": session.last_activity_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }
    if include_messages:
        data["messages"] = [message_to_dict(m) for m in session.messages]
        data["carried_over_context"] = session.carried_over_context or []
    return data


def _preview(session: ChatSession) -> str:
    for message in reversed(session.messages or []):
        if message.content.strip():
            text = " ".join(message.content.split())
            return text[:80]
    return session.summary[:80] if session.summary else ""


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "content": task.content,
        "status": task.status,
        "priority": task.priority,
        "progress": task.progress,
        "subtasks": task.subtasks or [],
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def memory_to_dict(memory: MemoryItem) -> dict:
    return {
        "id": memory.id,
        "key": memory.key,
        "value": memory.value,
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat(),
    }


def calendar_to_dict(event: CalendarEvent) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "event_type": event.event_type,
        "location": event.location,
        "created_at": event.created_at.isoformat(),
    }
