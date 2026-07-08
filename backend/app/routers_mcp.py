from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.models import McpServer, User
from backend.app.db.session import get_db
from backend.app.services.mcp import (
    get_user_mcp_server,
    list_mcp_servers,
    list_remote_tools,
    mcp_server_to_dict,
)


router = APIRouter(prefix="/mcp", tags=["mcp"])


class McpServerPayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    transport: Literal["streamable_http", "sse", "stdio"] = "streamable_http"
    url: str | None = Field(default=None, max_length=1000)
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    approval_required: bool = False
    timeout_seconds: int = Field(default=30, ge=3, le=120)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        stripped = value.strip()
        if not (stripped.startswith("http://") or stripped.startswith("https://")):
            raise ValueError("HTTP MCP URL must start with http:// or https://")
        return stripped


@router.get("/servers")
def servers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"servers": [mcp_server_to_dict(server) for server in list_mcp_servers(db, user)]}


@router.post("/servers")
def create_server(
    payload: McpServerPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = McpServer(
        user_id=user.id,
        name=payload.name.strip(),
        transport=payload.transport,
        url=payload.url,
        command=payload.command,
        args=payload.args,
        headers=payload.headers,
        enabled=payload.enabled,
        approval_required=payload.approval_required,
        timeout_seconds=payload.timeout_seconds,
    )
    db.add(server)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="MCP server name already exists")
    db.refresh(server)
    return {"server": mcp_server_to_dict(server)}


@router.put("/servers/{server_id}")
def update_server(
    server_id: str,
    payload: McpServerPayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = get_user_mcp_server(db, user, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    server.name = payload.name.strip()
    server.transport = payload.transport
    server.url = payload.url
    server.command = payload.command
    server.args = payload.args
    server.headers = payload.headers
    server.enabled = payload.enabled
    server.approval_required = payload.approval_required
    server.timeout_seconds = payload.timeout_seconds
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="MCP server name already exists")
    db.refresh(server)
    return {"server": mcp_server_to_dict(server)}


@router.delete("/servers/{server_id}")
def delete_server(
    server_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = get_user_mcp_server(db, user, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    db.delete(server)
    db.commit()
    return {"success": True}


@router.get("/servers/{server_id}/tools")
def server_tools(
    server_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    server = get_user_mcp_server(db, user, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    try:
        tools = list_remote_tools(server)
        server.last_error = None
        db.commit()
    except Exception as exc:
        server.last_error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc))
    return {"tools": tools}
