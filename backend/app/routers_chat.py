from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.chat.locks import get_session_lock
from backend.app.chat.orchestrator import agent_orchestrator
from backend.app.core.app_logging import new_trace_id
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.chat import ChatStreamRequest
from backend.app.services.sessions import get_or_create_current_session, get_session, set_current_session


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(
    payload: ChatStreamRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.message.strip() and not payload.images:
        raise HTTPException(status_code=400, detail="message is empty")

    if payload.session_id:
        session = get_session(db, user, payload.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        set_current_session(db, user, session)
    else:
        session = get_or_create_current_session(db, user)

    lock = get_session_lock(user.id, session.id)
    trace_id = new_trace_id("chat")

    async def event_stream() -> AsyncIterator[bytes]:
        async with lock:
            yield json.dumps({"type": "trace", "data": {"trace_id": trace_id}}, ensure_ascii=False).encode("utf-8") + b"\n"
            async for event in agent_orchestrator.stream_turn(
                db,
                user,
                session,
                payload.message,
                route_hint=payload.route,
                images=[img.model_dump() for img in payload.images],
                trace_id=trace_id,
            ):
                yield json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n"
            yield json.dumps({"type": "end", "data": None}, ensure_ascii=False).encode("utf-8") + b"\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
