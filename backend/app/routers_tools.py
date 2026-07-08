from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.tools.registry import list_tools, set_tool_enabled


router = APIRouter(prefix="/tools", tags=["tools"])


class ToolToggleRequest(BaseModel):
    name: str
    enabled: bool


@router.get("")
def tools(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"tools": list_tools(db, user)}


@router.post("/toggle")
def toggle_tool(payload: ToolToggleRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        set_tool_enabled(db, user, payload.name, payload.enabled)
    except KeyError:
        raise HTTPException(status_code=404, detail="tool not found")
    return {"success": True, "tools": list_tools(db, user)}

