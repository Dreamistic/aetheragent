from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.auth.dependencies import get_current_user
from backend.app.core.app_logging import read_recent_events
from backend.app.db.models import User


router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/events")
def recent_events(
    limit: int = Query(default=200, ge=1, le=1000),
    _: User = Depends(get_current_user),
):
    return {"events": read_recent_events(limit)}
