from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.chat import FavoriteRequest, NewSessionRequest
from backend.app.services.serializers import session_to_dict
from backend.app.services.sessions import create_session, get_or_create_current_session, get_session, list_sessions, set_current_session
from backend.app.services.users import ensure_user_settings


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
def sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = ensure_user_settings(db, user)
    return {
        "sessions": [session_to_dict(item) for item in list_sessions(db, user)],
        "current_session_id": settings.current_session_id,
    }


@router.get("/current")
def current_session(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_or_create_current_session(db, user)
    return session_to_dict(session, include_messages=True)


@router.post("/new")
def new_session(payload: NewSessionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = create_session(db, user, auto_summarize=payload.auto_summarize)
    return session_to_dict(session, include_messages=True)


@router.post("/switch")
def switch_session(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    session = get_session(db, user, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    set_current_session(db, user, session)
    return session_to_dict(session, include_messages=True)


@router.post("/{session_id}/favorite")
def favorite_session(
    session_id: str,
    payload: FavoriteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session(db, user, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    session.is_favorite = payload.is_favorite
    db.commit()
    db.refresh(session)
    return session_to_dict(session)

