from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.app_logging import log_event
from backend.app.db.models import McpServer, User


MCP_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_HTTP_TRANSPORTS = {"streamable_http", "sse"}
SUPPORTED_TRANSPORTS = SUPPORTED_HTTP_TRANSPORTS | {"stdio"}


@dataclass(frozen=True)
class McpToolDefinition:
    function_name: str
    server_id: str
    server_name: str
    tool_name: str
    description: str
    input_schema: dict[str, Any]


def slugify_mcp_name(value: str, *, fallback: str = "tool") -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return (slug or fallback)[:48]


def function_name_for(server: McpServer, tool_name: str) -> str:
    server_slug = slugify_mcp_name(server.name, fallback=server.id.replace("mcp_", "mcp"))
    tool_slug = slugify_mcp_name(tool_name, fallback="tool")
    return f"mcp__{server_slug}__{tool_slug}"[:64]


def mcp_server_to_dict(server: McpServer) -> dict[str, Any]:
    return {
        "id": server.id,
        "name": server.name,
        "transport": server.transport,
        "url": server.url,
        "command": server.command,
        "args": server.args or [],
        "headers": server.headers or {},
        "enabled": server.enabled,
        "approval_required": server.approval_required,
        "timeout_seconds": server.timeout_seconds,
        "last_error": server.last_error,
    }


def list_mcp_servers(db: Session, user: User, *, enabled_only: bool = False) -> list[McpServer]:
    stmt = select(McpServer).where(McpServer.user_id == user.id).order_by(McpServer.created_at.desc())
    if enabled_only:
        stmt = stmt.where(McpServer.enabled.is_(True))
    return list(db.execute(stmt).scalars().all())


def get_user_mcp_server(db: Session, user: User, server_id: str) -> McpServer | None:
    return db.execute(
        select(McpServer).where(McpServer.id == server_id, McpServer.user_id == user.id)
    ).scalar_one_or_none()


def normalize_mcp_input_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return {"type": "object", "properties": {}, "additionalProperties": True}
    normalized = dict(schema)
    normalized.setdefault("properties", {})
    normalized.setdefault("additionalProperties", True)
    return normalized


def list_mcp_tool_definitions(db: Session, user: User) -> list[McpToolDefinition]:
    definitions: list[McpToolDefinition] = []
    for server in list_mcp_servers(db, user, enabled_only=True):
        try:
            log_event("mcp", "tools_list_start", user_id=user.id, server_id=server.id, server_name=server.name)
            tools = list_remote_tools(server)
            server.last_error = None
            db.commit()
            log_event(
                "mcp",
                "tools_list_ok",
                user_id=user.id,
                server_id=server.id,
                server_name=server.name,
                tool_count=len(tools),
            )
        except Exception as exc:
            server.last_error = str(exc)
            db.commit()
            log_event(
                "mcp",
                "tools_list_error",
                user_id=user.id,
                server_id=server.id,
                server_name=server.name,
                error=str(exc),
            )
            continue
        for tool in tools:
            tool_name = str(tool.get("name") or "").strip()
            if not tool_name:
                continue
            definitions.append(
                McpToolDefinition(
                    function_name=function_name_for(server, tool_name),
                    server_id=server.id,
                    server_name=server.name,
                    tool_name=tool_name,
                    description=str(tool.get("description") or f"MCP tool {tool_name}"),
                    input_schema=normalize_mcp_input_schema(tool.get("inputSchema") or tool.get("input_schema")),
                )
            )
    return definitions


def execute_mcp_function(db: Session, user: User, function_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    for server in list_mcp_servers(db, user, enabled_only=True):
        try:
            tools = list_remote_tools(server)
        except Exception as exc:
            server.last_error = str(exc)
            db.commit()
            continue
        for tool in tools:
            tool_name = str(tool.get("name") or "")
            if function_name_for(server, tool_name) != function_name:
                continue
            try:
                log_event(
                    "mcp",
                    "tool_call_start",
                    user_id=user.id,
                    server_id=server.id,
                    server_name=server.name,
                    function_name=function_name,
                    tool_name=tool_name,
                    arguments=arguments,
                )
                result = call_remote_tool(server, tool_name, arguments)
                server.last_error = None
                db.commit()
                log_event(
                    "mcp",
                    "tool_call_ok",
                    user_id=user.id,
                    server_id=server.id,
                    server_name=server.name,
                    function_name=function_name,
                    tool_name=tool_name,
                    result=result,
                )
                return {"ok": True, "server": server.name, "tool": tool_name, "result": result}
            except Exception as exc:
                server.last_error = str(exc)
                db.commit()
                log_event(
                    "mcp",
                    "tool_call_error",
                    user_id=user.id,
                    server_id=server.id,
                    server_name=server.name,
                    function_name=function_name,
                    tool_name=tool_name,
                    error=str(exc),
                )
                return {"ok": False, "server": server.name, "tool": tool_name, "error": str(exc)}
    return {"ok": False, "error": f"MCP tool not found or server disabled: {function_name}"}


def list_remote_tools(server: McpServer) -> list[dict[str, Any]]:
    if server.transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(f"Unsupported MCP transport: {server.transport}")
    result = (
        _mcp_stdio_request(server, "tools/list", {})
        if server.transport == "stdio"
        else _mcp_http_request(server, "tools/list", {})
    )
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise ValueError("MCP tools/list response did not contain a tools array")
    return [item for item in tools if isinstance(item, dict)]


def call_remote_tool(server: McpServer, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if server.transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(f"Unsupported MCP transport: {server.transport}")
    params = {"name": tool_name, "arguments": arguments}
    if server.transport == "stdio":
        return _mcp_stdio_request(server, "tools/call", params)
    return _mcp_http_request(server, "tools/call", params)


def _mcp_http_request(server: McpServer, method: str, params: dict[str, Any]) -> dict[str, Any]:
    if not server.url:
        raise ValueError("MCP server URL is required for HTTP transports")
    timeout = max(3, min(int(server.timeout_seconds or 30), 120))
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        session_id = _initialize_http_session(client, server)
        return _post_jsonrpc(client, server, method, params, session_id=session_id)


def _initialize_http_session(client: httpx.Client, server: McpServer) -> str | None:
    payload = {
        "jsonrpc": "2.0",
        "id": "init",
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "vaeagent", "version": "0.1.0"},
        },
    }
    response = _raw_post(client, server, payload)
    session_id = response.headers.get("mcp-session-id")
    _parse_jsonrpc_response(response)
    notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    try:
        _raw_post(client, server, notification, session_id=session_id)
    except httpx.HTTPError:
        pass
    return session_id


def _post_jsonrpc(
    client: httpx.Client,
    server: McpServer,
    method: str,
    params: dict[str, Any],
    *,
    session_id: str | None,
) -> dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": "call", "method": method, "params": params}
    response = _raw_post(client, server, payload, session_id=session_id)
    return _parse_jsonrpc_response(response)


def _raw_post(
    client: httpx.Client,
    server: McpServer,
    payload: dict[str, Any],
    *,
    session_id: str | None = None,
) -> httpx.Response:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
    }
    for key, value in (server.headers or {}).items():
        if key and value is not None:
            headers[str(key)] = str(value)
    if session_id:
        headers["mcp-session-id"] = session_id
    response = client.post(str(server.url), json=payload, headers=headers)
    response.raise_for_status()
    return response


def _parse_jsonrpc_response(response: httpx.Response) -> dict[str, Any]:
    text = response.text.strip()
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type or text.startswith("event:") or text.startswith("data:"):
        data = _parse_sse_json(text)
    else:
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError("MCP response is not a JSON object")
    if data.get("error"):
        raise ValueError(json.dumps(data["error"], ensure_ascii=False))
    result = data.get("result")
    if isinstance(result, dict):
        return result
    if result is None:
        return {}
    return {"value": result}


def _parse_sse_json(text: str) -> dict[str, Any]:
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            value = line.removeprefix("data:").strip()
            if value and value != "[DONE]":
                data_lines.append(value)
    for item in data_lines:
        try:
            decoded = json.loads(item)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return decoded
    raise ValueError("No JSON-RPC payload found in MCP SSE response")


def _mcp_stdio_request(server: McpServer, method: str, params: dict[str, Any]) -> dict[str, Any]:
    if not server.command:
        raise ValueError("MCP stdio command is required")
    timeout = max(3, min(int(server.timeout_seconds or 30), 120))
    command = [server.command, *[str(arg) for arg in (server.args or [])]]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        _stdio_send(
            process,
            {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "vaeagent", "version": "0.1.0"},
                },
            },
        )
        _stdio_read_response(process, "init", timeout)
        _stdio_send(process, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        call_id = "call"
        _stdio_send(process, {"jsonrpc": "2.0", "id": call_id, "method": method, "params": params})
        return _stdio_read_response(process, call_id, timeout)
    finally:
        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            process.kill()


def _stdio_send(process: subprocess.Popen, payload: dict[str, Any]) -> None:
    if process.stdin is None:
        raise ValueError("MCP stdio stdin is not available")
    process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    process.stdin.flush()


def _stdio_read_response(process: subprocess.Popen, call_id: str, timeout_seconds: int) -> dict[str, Any]:
    if process.stdout is None:
        raise ValueError("MCP stdio stdout is not available")
    deadline = time.monotonic() + timeout_seconds
    stderr_tail = ""
    while time.monotonic() < deadline:
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                stderr_tail = _safe_read_stderr(process)
                raise ValueError(f"MCP stdio process exited early. {stderr_tail}".strip())
            time.sleep(0.02)
            continue
        decoded = _parse_stdio_line_or_header(process, line)
        if not decoded:
            continue
        if decoded.get("id") != call_id:
            continue
        if decoded.get("error"):
            raise ValueError(json.dumps(decoded["error"], ensure_ascii=False))
        result = decoded.get("result")
        if isinstance(result, dict):
            return result
        if result is None:
            return {}
        return {"value": result}
    stderr_tail = _safe_read_stderr(process)
    raise TimeoutError(f"MCP stdio timeout waiting for {call_id}. {stderr_tail}".strip())


def _parse_stdio_line_or_header(process: subprocess.Popen, line: str) -> dict[str, Any] | None:
    text = line.strip()
    if not text:
        return None
    if text.lower().startswith("content-length:"):
        if process.stdout is None:
            return None
        try:
            length = int(text.split(":", 1)[1].strip())
        except ValueError:
            return None
        while True:
            header = process.stdout.readline()
            if header in {"\r\n", "\n", ""}:
                break
        body = process.stdout.read(length)
        return json.loads(body)
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _safe_read_stderr(process: subprocess.Popen) -> str:
    try:
        if process.poll() is None:
            return ""
        if process.stderr is None:
            return ""
        return process.stderr.read()[-1000:]
    except Exception:
        return ""
