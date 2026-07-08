from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.app_logging import log_event
from backend.app.core.config import get_settings
from backend.app.db.models import CalendarEvent, MemoryItem, Task, ToolSetting, User
from backend.app.services.mcp import execute_mcp_function, list_mcp_tool_definitions
from backend.app.services.serializers import calendar_to_dict, memory_to_dict, task_to_dict


ToolHandler = Callable[["ToolContext", dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    strict: bool = True

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
                "strict": self.strict,
            },
        }


@dataclass
class ToolContext:
    db: Session
    user: User
    session_id: str


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _create_task(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    priority = args.get("priority") or "medium"
    task = Task(user_id=ctx.user.id, content=str(args["content"]), priority=str(priority))
    ctx.db.add(task)
    ctx.db.commit()
    ctx.db.refresh(task)
    return {"ok": True, "task": task_to_dict(task)}


def _list_tasks(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    status = args.get("status")
    stmt = select(Task).where(Task.user_id == ctx.user.id)
    if status:
        stmt = stmt.where(Task.status == status)
    tasks = list(ctx.db.execute(stmt.order_by(Task.created_at.desc())).scalars().all())
    return {"ok": True, "tasks": [task_to_dict(t) for t in tasks]}


def _update_task_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    task = ctx.db.get(Task, args["task_id"])
    if not task or task.user_id != ctx.user.id:
        return {"ok": False, "error": "task not found"}
    task.status = args.get("status") or task.status
    if args.get("progress") is not None:
        task.progress = int(args["progress"])
    ctx.db.commit()
    ctx.db.refresh(task)
    return {"ok": True, "task": task_to_dict(task)}


def _save_memory(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    item = MemoryItem(user_id=ctx.user.id, key=str(args["key"]), value=str(args["value"]))
    ctx.db.add(item)
    ctx.db.commit()
    ctx.db.refresh(item)
    return {"ok": True, "memory": memory_to_dict(item)}


def _list_memories(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    stmt = select(MemoryItem).where(MemoryItem.user_id == ctx.user.id).order_by(MemoryItem.updated_at.desc())
    memories = list(ctx.db.execute(stmt).scalars().all())
    return {"ok": True, "memories": [memory_to_dict(m) for m in memories]}


def _add_calendar_event(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    event = CalendarEvent(
        user_id=ctx.user.id,
        title=str(args["title"]),
        start_time=str(args["start_time"]),
        end_time=args.get("end_time"),
        description=args.get("description"),
        event_type=args.get("event_type") or "personal",
        location=args.get("location"),
    )
    ctx.db.add(event)
    ctx.db.commit()
    ctx.db.refresh(event)
    return {"ok": True, "event": calendar_to_dict(event)}


def _list_calendar_events(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    date_prefix = args.get("date")
    stmt = select(CalendarEvent).where(CalendarEvent.user_id == ctx.user.id)
    if date_prefix:
        stmt = stmt.where(CalendarEvent.start_time.like(f"{date_prefix}%"))
    events = list(ctx.db.execute(stmt.order_by(CalendarEvent.start_time.asc())).scalars().all())
    return {"ok": True, "events": [calendar_to_dict(e) for e in events]}


def _ask_for_info(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    call_id = f"ask_{uuid.uuid4().hex}"
    return {
        "ok": True,
        "pending": True,
        "event_type": "ask_for_info_request",
        "request": {
            "call_id": call_id,
            "function_name": "ask_for_info",
            "session_id": ctx.session_id,
            "payload": {
                "call_id": call_id,
                "meta": {"title": args.get("title"), "layout": args.get("layout") or "flat"},
                "questions": args.get("questions") or [],
            },
        },
    }


def _ask_for_confirmation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    call_id = f"confirm_{uuid.uuid4().hex}"
    return {
        "ok": True,
        "pending": True,
        "event_type": "confirmation_request",
        "request": {
            "call_id": call_id,
            "function_name": "ask_for_confirmation",
            "session_id": ctx.session_id,
            "payload": {
                "call_id": call_id,
                "type": "confirmation",
                "description": args.get("description") or "",
            },
        },
    }


TOOL_SPECS: dict[str, ToolSpec] = {
    "create_task": ToolSpec(
        "create_task",
        "Create a task for the current signed-in user.",
        _schema(
            {
                "content": {"type": "string", "description": "Task content."},
                "priority": {"type": ["string", "null"], "enum": ["high", "medium", "low", None], "description": "Task priority."},
            },
            ["content", "priority"],
        ),
        _create_task,
    ),
    "list_tasks": ToolSpec(
        "list_tasks",
        "List tasks for the current signed-in user.",
        _schema(
            {"status": {"type": ["string", "null"], "enum": ["pending", "in_progress", "completed", None]}},
            ["status"],
        ),
        _list_tasks,
    ),
    "update_task_status": ToolSpec(
        "update_task_status",
        "Update task status or progress for the current signed-in user.",
        _schema(
            {
                "task_id": {"type": "string"},
                "status": {"type": ["string", "null"], "enum": ["pending", "in_progress", "completed", None]},
                "progress": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
            },
            ["task_id", "status", "progress"],
        ),
        _update_task_status,
    ),
    "save_memory": ToolSpec(
        "save_memory",
        "Save a user-specific memory item.",
        _schema({"key": {"type": "string"}, "value": {"type": "string"}}, ["key", "value"]),
        _save_memory,
    ),
    "list_memories": ToolSpec(
        "list_memories",
        "List user-specific memory items.",
        _schema({}, []),
        _list_memories,
    ),
    "add_calendar_event": ToolSpec(
        "add_calendar_event",
        "Add a calendar event for the current signed-in user.",
        _schema(
            {
                "title": {"type": "string"},
                "start_time": {"type": "string", "description": "Start time, e.g. 2026-07-05 14:00."},
                "end_time": {"type": ["string", "null"]},
                "description": {"type": ["string", "null"]},
                "event_type": {"type": ["string", "null"], "enum": ["class", "work", "personal", "reminder", "anniversary", None]},
                "location": {"type": ["string", "null"]},
            },
            ["title", "start_time", "end_time", "description", "event_type", "location"],
        ),
        _add_calendar_event,
    ),
    "list_calendar_events": ToolSpec(
        "list_calendar_events",
        "List calendar events. Optionally filter by date prefix such as 2026-07-05.",
        _schema({"date": {"type": ["string", "null"]}}, ["date"]),
        _list_calendar_events,
    ),
    "ask_for_info": ToolSpec(
        "ask_for_info",
        "Ask the user for structured information through the client UI.",
        _schema(
            {
                "title": {"type": ["string", "null"]},
                "layout": {"type": ["string", "null"], "enum": ["flat", "steps", None]},
                "questions": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
            },
            ["title", "layout", "questions"],
        ),
        _ask_for_info,
        False,
    ),
    "ask_for_confirmation": ToolSpec(
        "ask_for_confirmation",
        "Ask the user to approve a sensitive or important operation before proceeding.",
        _schema({"description": {"type": "string"}}, ["description"]),
        _ask_for_confirmation,
    ),
}


def ensure_tool_settings(db: Session, user: User) -> None:
    configured = {
        row.tool_name: row
        for row in db.execute(select(ToolSetting).where(ToolSetting.user_id == user.id)).scalars().all()
    }
    defaults = get_settings().default_tool_enabled
    changed = False
    for name in TOOL_SPECS:
        if name not in configured:
            db.add(ToolSetting(user_id=user.id, tool_name=name, enabled=bool(defaults.get(name, True))))
            changed = True
    if changed:
        db.commit()


def list_tools(db: Session, user: User) -> list[dict[str, Any]]:
    ensure_tool_settings(db, user)
    states = {
        row.tool_name: row.enabled
        for row in db.execute(select(ToolSetting).where(ToolSetting.user_id == user.id)).scalars().all()
    }
    tools = [
        {"name": spec.name, "description": spec.description, "enabled": bool(states.get(spec.name, True))}
        for spec in TOOL_SPECS.values()
    ]
    if get_settings().mcp_enabled:
        for tool in list_mcp_tool_definitions(db, user):
            tools.append(
                {
                    "name": tool.function_name,
                    "description": tool.description,
                    "enabled": True,
                    "source": "mcp",
                    "server_name": tool.server_name,
                }
            )
    return tools


def enabled_tool_specs(db: Session, user: User) -> list[ToolSpec]:
    ensure_tool_settings(db, user)
    states = {
        row.tool_name: row.enabled
        for row in db.execute(select(ToolSetting).where(ToolSetting.user_id == user.id)).scalars().all()
    }
    enabled_names = {name for name, enabled in states.items() if enabled}
    builtin_specs = [spec for name, spec in TOOL_SPECS.items() if name in enabled_names]
    mcp_specs: list[ToolSpec] = []
    if not get_settings().mcp_enabled:
        return builtin_specs
    for tool in list_mcp_tool_definitions(db, user):
        def _handler(ctx: ToolContext, args: dict[str, Any], function_name: str = tool.function_name) -> dict[str, Any]:
            return execute_mcp_function(ctx.db, ctx.user, function_name, args)

        mcp_specs.append(
            ToolSpec(
                tool.function_name,
                f"MCP tool from server '{tool.server_name}': {tool.description}",
                tool.input_schema,
                _handler,
                strict=False,
            )
        )
    return builtin_specs + mcp_specs


def set_tool_enabled(db: Session, user: User, name: str, enabled: bool) -> None:
    if name not in TOOL_SPECS:
        raise KeyError(name)
    ensure_tool_settings(db, user)
    row = db.execute(
        select(ToolSetting).where(ToolSetting.user_id == user.id, ToolSetting.tool_name == name)
    ).scalar_one()
    row.enabled = enabled
    db.commit()


def execute_tool(ctx: ToolContext, name: str, arguments_json: str) -> dict[str, Any]:
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid arguments json: {exc}"}
    try:
        if name.startswith("mcp__"):
            return execute_mcp_function(ctx.db, ctx.user, name, args)
        if name not in TOOL_SPECS:
            return {"ok": False, "error": f"unknown tool: {name}"}
        return TOOL_SPECS[name].handler(ctx, args)
    except Exception as exc:
        log_event(
            "tool",
            "handler_error",
            user_id=ctx.user.id,
            session_id=ctx.session_id,
            tool_name=name,
            arguments=args,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return {"ok": False, "error": str(exc), "error_type": type(exc).__name__}


def render_tool_docs(specs: list[ToolSpec]) -> str:
    lines: list[str] = []
    for spec in specs:
        parameters = spec.parameters or {}
        properties = parameters.get("properties") or {}
        required = set(parameters.get("required") or [])
        signature_parts = []
        for name, schema in properties.items():
            type_name = schema.get("type", "any") if isinstance(schema, dict) else "any"
            if isinstance(type_name, list):
                type_name = " | ".join(str(item) for item in type_name)
            marker = "" if name in required else " = null"
            signature_parts.append(f"{name}: {type_name}{marker}")
        lines.append(f"### {spec.name}({', '.join(signature_parts)})")
        lines.append(f"- description: {spec.description}")
        if required:
            lines.append(f"- required: {', '.join(name for name in properties if name in required)}")
        if properties:
            lines.append("- parameters:")
            for name, schema in properties.items():
                if not isinstance(schema, dict):
                    lines.append(f"  - {name}: {schema}")
                    continue
                description = schema.get("description") or ""
                enum = schema.get("enum")
                enum_text = f"; enum={json.dumps(enum, ensure_ascii=False)}" if enum else ""
                type_text = schema.get("type", "any")
                lines.append(f"  - {name}: type={json.dumps(type_text, ensure_ascii=False)}{enum_text}; {description}".rstrip())
        lines.append(
            "- textual fallback example:\n"
            f"  <function_calls>\n"
            f"    <invoke name=\"{spec.name}\">\n"
            f"      <!-- one <parameter name=\"...\">value</parameter> per argument -->\n"
            f"    </invoke>\n"
            f"  </function_calls>"
        )
        lines.append("")
    return "\n".join(lines)
