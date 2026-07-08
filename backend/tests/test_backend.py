from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    monkeypatch.setenv("VAEAGENT_DATABASE_URL", f"sqlite:///{db_file.name}")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    from backend.app.db import session as db_session
    from backend.app.db.models import Base

    db_session.engine.dispose()
    db_session.engine = db_session.create_engine(
        get_settings().database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    db_session.SessionLocal.configure(bind=db_session.engine)
    Base.metadata.create_all(bind=db_session.engine)

    from backend.app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    try:
        os.remove(db_file.name)
    except OSError:
        pass


def register(client: TestClient, username: str, email: str | None = None) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123", "email": email},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_user_isolation(client: TestClient):
    alice = register(client, "alice", "alice@example.local")
    bob = register(client, "bob", "bob@example.local")

    alice_session = client.get("/api/sessions/current", headers=auth(alice["access_token"]))
    bob_session = client.get("/api/sessions/current", headers=auth(bob["access_token"]))
    assert alice_session.status_code == 200
    assert bob_session.status_code == 200
    assert alice_session.json()["session_id"] != bob_session.json()["session_id"]

    login = client.post(
        "/api/auth/login",
        json={"username_or_email": "alice@example.local", "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["username"] == "alice"


def test_sessions_new_switch_and_favorite(client: TestClient):
    user = register(client, "session-user")
    headers = auth(user["access_token"])

    current = client.get("/api/sessions/current", headers=headers).json()
    new_session = client.post("/api/sessions/new", headers=headers, json={"auto_summarize": True}).json()
    assert new_session["session_id"] != current["session_id"]

    switched = client.post("/api/sessions/switch", headers=headers, json={"session_id": current["session_id"]})
    assert switched.status_code == 200
    assert switched.json()["session_id"] == current["session_id"]

    favorite = client.post(
        f"/api/sessions/{current['session_id']}/favorite",
        headers=headers,
        json={"is_favorite": True},
    )
    assert favorite.status_code == 200
    assert favorite.json()["is_favorite"] is True


def test_settings_and_tools(client: TestClient):
    user = register(client, "settings-user")
    headers = auth(user["access_token"])

    settings = client.put("/api/settings", headers=headers, json={"locale": "zh-Hant", "theme": "dark"})
    assert settings.status_code == 200
    assert settings.json()["settings"]["locale"] == "zh-Hant"

    tools = client.get("/api/tools", headers=headers)
    assert tools.status_code == 200
    first_tool = tools.json()["tools"][0]
    toggled = client.post(
        "/api/tools/toggle",
        headers=headers,
        json={"name": first_tool["name"], "enabled": False},
    )
    assert toggled.status_code == 200
    assert any(item["name"] == first_tool["name"] and item["enabled"] is False for item in toggled.json()["tools"])


def test_update_profile_username_and_avatar(client: TestClient):
    user = register(client, "profile-user")
    headers = auth(user["access_token"])
    avatar = "data:image/png;base64,ZmFrZQ=="

    updated = client.put(
        "/api/auth/profile",
        headers=headers,
        json={"username": "profile-user-new", "display_name": "Profile User", "avatar_data": avatar},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["user"]["username"] == "profile-user-new"
    assert updated.json()["user"]["display_name"] == "Profile User"
    assert updated.json()["user"]["avatar_data"] == avatar

    duplicate = register(client, "profile-duplicate")
    duplicate_update = client.put(
        "/api/auth/profile",
        headers=auth(duplicate["access_token"]),
        json={"username": "profile-user-new"},
    )
    assert duplicate_update.status_code == 409


def test_mcp_server_crud_is_user_scoped(client: TestClient):
    alice = register(client, "mcp-alice")
    bob = register(client, "mcp-bob")
    alice_headers = auth(alice["access_token"])
    bob_headers = auth(bob["access_token"])

    created = client.post(
        "/api/mcp/servers",
        headers=alice_headers,
        json={
            "name": "local-tools",
            "transport": "streamable_http",
            "url": "http://127.0.0.1:9000/mcp",
            "headers": {"Authorization": "Bearer test"},
            "enabled": True,
        },
    )
    assert created.status_code == 200, created.text
    server_id = created.json()["server"]["id"]

    alice_list = client.get("/api/mcp/servers", headers=alice_headers)
    bob_list = client.get("/api/mcp/servers", headers=bob_headers)
    assert len(alice_list.json()["servers"]) == 1
    assert bob_list.json()["servers"] == []

    updated = client.put(
        f"/api/mcp/servers/{server_id}",
        headers=alice_headers,
        json={
            "name": "local-tools",
            "transport": "streamable_http",
            "url": "http://127.0.0.1:9000/mcp",
            "headers": {},
            "enabled": False,
            "timeout_seconds": 10,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["server"]["enabled"] is False

    bob_delete = client.delete(f"/api/mcp/servers/{server_id}", headers=bob_headers)
    assert bob_delete.status_code == 404

    deleted = client.delete(f"/api/mcp/servers/{server_id}", headers=alice_headers)
    assert deleted.status_code == 200


def test_chat_stream_fallback_ndjson(client: TestClient):
    user = register(client, "chat-user")
    headers = auth(user["access_token"])

    with client.stream(
        "POST",
        "/api/chat/stream",
        headers=headers,
        json={"message": "请用 Markdown 和 $a^2+b^2=c^2$ 回复"},
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    event_types = [event["type"] for event in events]
    assert "route" in event_types
    assert "token" in event_types
    assert "final" in event_types
    assert event_types[-1] == "end"

    current = client.get("/api/sessions/current", headers=headers).json()
    roles = [message["role"] for message in current["messages"]]
    assert roles.count("user") == 1
    assert roles.count("assistant") == 1


def test_chat_stream_openai_events_are_emitted(client: TestClient, monkeypatch):
    user = register(client, "openai-stream-user")
    headers = auth(user["access_token"])

    from backend.app.chat.orchestrator import agent_orchestrator

    monkeypatch.setattr(agent_orchestrator.settings, "openai_api_key", "fake-key")

    async def fake_stream_once(client, messages, tools, *, tool_names, yield_token, forced_tool_name=None):
        yield {"type": "token", "data": "模拟"}
        yield {"type": "token", "data": "模型回复"}
        yield {"type": "_openai_done", "data": {"text": "模拟模型回复", "tool_calls": []}}

    monkeypatch.setattr(agent_orchestrator, "_stream_openai_once", fake_stream_once)

    with client.stream(
        "POST",
        "/api/chat/stream",
        headers=headers,
        json={"message": "触发真实模型路径"},
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    assert [event["type"] for event in events].count("api_error") == 0
    token_events = [event["data"] for event in events if event["type"] == "token"]
    assert token_events == ["模拟", "模型回复"]

    current = client.get("/api/sessions/current", headers=headers).json()
    roles = [message["role"] for message in current["messages"]]
    assert roles.count("user") == 1
    assert roles.count("assistant") == 1


def test_chat_stream_pending_tool_request_stops_for_client_input(client: TestClient, monkeypatch):
    user = register(client, "pending-tool-user")
    headers = auth(user["access_token"])

    from backend.app.chat.orchestrator import agent_orchestrator

    monkeypatch.setattr(agent_orchestrator.settings, "openai_api_key", "fake-key")

    async def fake_stream_once(client, messages, tools, *, tool_names, yield_token, forced_tool_name=None):
        assert forced_tool_name == "ask_for_info"
        yield {
            "type": "_openai_done",
            "data": {
                "text": "",
                "tool_calls": [
                    {
                        "id": "call_ask",
                        "type": "function",
                        "function": {
                            "name": "ask_for_info",
                            "arguments": json.dumps(
                                {
                                    "title": "功能测试",
                                    "layout": "flat",
                                    "questions": [{"id": "name", "label": "姓名"}],
                                },
                                ensure_ascii=False,
                            ),
                        },
                    }
                ],
            },
        }

    monkeypatch.setattr(agent_orchestrator, "_stream_openai_once", fake_stream_once)

    with client.stream(
        "POST",
        "/api/chat/stream",
        headers=headers,
        json={"message": "测试 ask_for_info"},
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    event_types = [event["type"] for event in events]
    assert "tool_call" in event_types
    assert "ask_for_info_request" in event_types
    assert "tool_result" in event_types
    assert "final" in event_types
    assert event_types.index("ask_for_info_request") < event_types.index("final")
    final_event = next(event for event in events if event["type"] == "final")
    assert "补充" in final_event["data"] or "表单" in final_event["data"]


def test_chat_stream_text_tool_call_executes_and_continues(client: TestClient, monkeypatch):
    user = register(client, "text-tool-user")
    headers = auth(user["access_token"])

    from backend.app.chat.orchestrator import agent_orchestrator

    monkeypatch.setattr(agent_orchestrator.settings, "openai_api_key", "fake-key")
    calls = {"count": 0}

    async def fake_stream_once(client, messages, tools, *, tool_names, yield_token, forced_tool_name=None):
        calls["count"] += 1
        if calls["count"] == 1:
            assert "create_task" in tool_names
            yield {
                "type": "_openai_done",
                "data": {
                    "text": """
<function_calls>
  <invoke name="create_task">
    <parameter name="content">写一条工具链测试任务</parameter>
    <parameter name="priority">high</parameter>
  </invoke>
</function_calls>
""",
                    "tool_calls": [],
                },
            }
            return
        assert any(message.get("role") == "tool" for message in messages)
        yield {"type": "token", "data": "任务已创建"}
        yield {"type": "_openai_done", "data": {"text": "任务已创建", "tool_calls": []}}

    monkeypatch.setattr(agent_orchestrator, "_stream_openai_once", fake_stream_once)

    with client.stream(
        "POST",
        "/api/chat/stream",
        headers=headers,
        json={"message": "请调用 create_task 创建任务"},
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    event_types = [event["type"] for event in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "final" in event_types
    assert calls["count"] == 2
    tool_result = next(event for event in events if event["type"] == "tool_result")
    assert tool_result["data"]["result"]["ok"] is True

    current = client.get("/api/sessions/current", headers=headers).json()
    function_messages = [message for message in current["messages"] if message["role"] == "function"]
    assert any((message.get("meta") or {}).get("tool_payload", {}).get("type") == "tool_result" for message in function_messages)


def test_chat_stream_forced_tool_json_arguments_execute(client: TestClient, monkeypatch):
    user = register(client, "forced-json-tool-user")
    headers = auth(user["access_token"])

    from backend.app.chat.orchestrator import agent_orchestrator

    monkeypatch.setattr(agent_orchestrator.settings, "openai_api_key", "fake-key")
    calls = {"count": 0}

    async def fake_stream_once(client, messages, tools, *, tool_names, yield_token, forced_tool_name=None):
        calls["count"] += 1
        if calls["count"] == 1:
            assert forced_tool_name == "create_task"
            yield {
                "type": "_openai_done",
                "data": {
                    "text": json.dumps(
                        {"content": "这是来自裸 JSON 的任务", "priority": "low"},
                        ensure_ascii=False,
                    ),
                    "tool_calls": [],
                },
            }
            return
        assert any(message.get("role") == "tool" for message in messages)
        yield {"type": "token", "data": "已创建低优先级测试任务"}
        yield {"type": "_openai_done", "data": {"text": "已创建低优先级测试任务", "tool_calls": []}}

    monkeypatch.setattr(agent_orchestrator, "_stream_openai_once", fake_stream_once)

    with client.stream(
        "POST",
        "/api/chat/stream",
        headers=headers,
        json={"message": "测试一下功能，你试试create_tasks这个工具能否正常调用"},
    ) as response:
        assert response.status_code == 200
        events = [json.loads(line) for line in response.iter_lines() if line]

    event_types = [event["type"] for event in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert calls["count"] == 2
    final_event = next(event for event in events if event["type"] == "final")
    assert "已创建" in final_event["data"]
    assert '"content"' not in final_event["data"]
    tool_result = next(event for event in events if event["type"] == "tool_result")
    assert tool_result["data"]["result"]["task"]["content"] == "这是来自裸 JSON 的任务"


def test_mcp_stdio_tools_list_and_call(tmp_path: Path):
    script = tmp_path / "stdio_mcp.py"
    script.write_text(
        """
import json
import sys

for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":{"protocolVersion":"2025-06-18","capabilities":{} }}), flush=True)
    elif msg.get("method") == "notifications/initialized":
        continue
    elif msg.get("method") == "tools/list":
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":{"tools":[{"name":"echo","description":"Echo text","inputSchema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}]}}), flush=True)
    elif msg.get("method") == "tools/call":
        args = msg.get("params", {}).get("arguments", {})
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":{"content":[{"type":"text","text":args.get("text", "")}]}}), flush=True)
""",
        encoding="utf-8",
    )

    from backend.app.db.models import McpServer
    from backend.app.services.mcp import call_remote_tool, list_remote_tools

    server = McpServer(
        user_id="user_test",
        name="stdio-test",
        transport="stdio",
        command=sys.executable,
        args=[str(script)],
        timeout_seconds=5,
    )
    tools = list_remote_tools(server)
    assert tools[0]["name"] == "echo"
    result = call_remote_tool(server, "echo", {"text": "hello"})
    assert result["content"][0]["text"] == "hello"


def test_logs_endpoint_returns_events(client: TestClient):
    user = register(client, "logs-user")
    headers = auth(user["access_token"])

    from backend.app.core.app_logging import log_event

    log_event("test", "logs_endpoint_marker", marker="ok")
    response = client.get("/api/logs/events?limit=20", headers=headers)
    assert response.status_code == 200
    assert any(event.get("event") == "logs_endpoint_marker" for event in response.json()["events"])
