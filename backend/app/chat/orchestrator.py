from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from backend.app.chat.context_switch import perform_context_switch, should_switch_context
from backend.app.core.app_logging import log_event
from backend.app.core.config import get_settings
from backend.app.db.models import ChatSession, Message, User
from backend.app.services.prompts import build_system_prompt
from backend.app.services.routing import detect_route
from backend.app.services.sessions import add_message
from backend.app.services.users import ensure_user_settings
from backend.app.tools.call_parser import (
    TextToolCallFilter,
    extract_text_tool_calls,
    normalize_tool_call,
    parse_json_object_text,
)
from backend.app.tools.registry import ToolContext, ToolSpec, enabled_tool_specs, execute_tool, render_tool_docs


class AgentOrchestrator:
    def __init__(self):
        self.settings = get_settings()

    async def stream_turn(
        self,
        db: Session,
        user: User,
        session: ChatSession,
        user_message: str,
        *,
        route_hint: str | None = None,
        images: list[dict[str, Any]] | None = None,
        trace_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        user_db_message: Message | None = None
        trace_id = trace_id or "chat_untraced"
        try:
            route, route_detail = detect_route(user_message, route_hint)
            log_event(
                "chat",
                "turn_start",
                trace_id=trace_id,
                user_id=user.id,
                session_id=session.id,
                route=route,
                message_preview=user_message[:200],
                image_count=len(images or []),
            )
            yield {"type": "route", "data": {"route": route, "detail": route_detail}}
            user_db_message = add_message(
                db,
                user,
                session,
                "user",
                user_message,
                route=route,
                route_detail=route_detail,
                images=images or [],
            )

            tool_specs = enabled_tool_specs(db, user)
            user_settings = ensure_user_settings(db, user)
            log_event(
                "chat",
                "tools_loaded",
                trace_id=trace_id,
                user_id=user.id,
                session_id=session.id,
                tool_names=[spec.name for spec in tool_specs],
            )
            system_prompt = build_system_prompt(
                user_settings,
                session,
                render_tool_docs(tool_specs),
                route=route,
            )

            if not self.settings.openai_api_key:
                final_text = await self._fallback_stream(user_message, route, yield_event=lambda event: None)
                # _fallback_stream cannot yield through callback in Python async generators, so emit here.
                final_text = self._fallback_text(user_message, route)
                for chunk in _chunk_text(final_text, 16):
                    yield {"type": "token", "data": chunk}
                    await asyncio.sleep(0)
                add_message(db, user, session, "assistant", final_text, route=route)
                yield {"type": "final", "data": final_text}
                log_event(
                    "chat",
                    "turn_final",
                    trace_id=trace_id,
                    user_id=user.id,
                    session_id=session.id,
                    source="fallback",
                    final_chars=len(final_text),
                )
                async for event in self._maybe_switch_context(db, user, session):
                    yield event
                return

            final_text = ""
            db.refresh(session)
            api_messages = self._build_api_messages(system_prompt, session.messages)
            tools = [spec.openai_schema() for spec in tool_specs]
            tool_names = {spec.name for spec in tool_specs}
            forced_tool_name = self._detect_explicit_tool_request(user_message, tool_specs)
            client_kwargs: dict[str, Any] = {"api_key": self.settings.openai_api_key}
            if self.settings.openai_base_url:
                client_kwargs["base_url"] = self.settings.openai_base_url
            if self._is_openrouter:
                client_kwargs["default_headers"] = {
                    "HTTP-Referer": self.settings.openrouter_site_url,
                    "X-Title": self.settings.openrouter_app_name,
                }
            client = OpenAI(**client_kwargs)
            tool_context = ToolContext(db=db, user=user, session_id=session.id)

            for _round in range(self.settings.max_tool_rounds + 1):
                assistant_text = ""
                tool_calls: list[dict[str, Any]] = []
                log_event(
                    "chat",
                    "llm_stream_start",
                    trace_id=trace_id,
                    user_id=user.id,
                    session_id=session.id,
                    round=_round,
                    model=self.settings.openai_model,
                    forced_tool_name=forced_tool_name if _round == 0 else None,
                    tool_count=len(tools),
                )
                async for event in self._stream_openai_once(
                    client,
                    api_messages,
                    tools,
                    tool_names=tool_names,
                    yield_token=True,
                    forced_tool_name=forced_tool_name if _round == 0 else None,
                ):
                    if event["type"] == "_openai_done":
                        data = event["data"]
                        assistant_text = data["text"]
                        tool_calls = data["tool_calls"]
                        if not tool_calls:
                            parsed_calls, cleaned_text = extract_text_tool_calls(assistant_text, tool_names)
                            if parsed_calls:
                                assistant_text = cleaned_text
                                tool_calls = parsed_calls
                        if not tool_calls and _round == 0 and forced_tool_name:
                            forced_call = self._parse_forced_tool_arguments(
                                assistant_text,
                                forced_tool_name,
                                tool_specs,
                                trace_id=trace_id,
                                user_id=user.id,
                                session_id=session.id,
                            )
                            if forced_call:
                                assistant_text = ""
                                tool_calls = [forced_call]
                        log_event(
                            "chat",
                            "llm_stream_done",
                            trace_id=trace_id,
                            user_id=user.id,
                            session_id=session.id,
                            round=_round,
                            assistant_chars=len(assistant_text or ""),
                            tool_call_count=len(tool_calls),
                            assistant_preview=(assistant_text or "")[:240],
                        )
                        continue
                    yield event

                if not tool_calls:
                    final_text += assistant_text
                    break

                api_messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_text or None,
                        "tool_calls": tool_calls,
                    }
                )
                for call in tool_calls:
                    function = call.get("function") or {}
                    tool_name = function.get("name") or ""
                    arguments = function.get("arguments") or "{}"
                    tool_call_data = {"id": call.get("id"), "function_name": tool_name, "arguments": arguments}
                    log_event(
                        "tool",
                        "call_start",
                        trace_id=trace_id,
                        user_id=user.id,
                        session_id=session.id,
                        round=_round,
                        tool_call=tool_call_data,
                    )
                    self._record_tool_event(db, user, session, "tool_call", tool_call_data)
                    yield {"type": "tool_call", "data": tool_call_data}
                    result = execute_tool(tool_context, tool_name, arguments)
                    if result.get("pending"):
                        request_event_type = result.get("event_type", "ask_for_info_request")
                        request_data = result.get("request")
                        self._record_tool_event(db, user, session, request_event_type, request_data)
                        yield {"type": request_event_type, "data": request_data}
                    tool_result_data = {"tool_call_id": call.get("id"), "function_name": tool_name, "result": result}
                    self._record_tool_event(db, user, session, "tool_result", tool_result_data)
                    log_event(
                        "tool",
                        "call_done",
                        trace_id=trace_id,
                        user_id=user.id,
                        session_id=session.id,
                        round=_round,
                        tool_name=tool_name,
                        ok=result.get("ok"),
                        pending=result.get("pending", False),
                        result=result,
                    )
                    yield {"type": "tool_result", "data": tool_result_data}
                    if result.get("pending"):
                        final_text += assistant_text.strip() or self._pending_tool_message(result)
                        add_message(db, user, session, "assistant", final_text, route=route)
                        yield {"type": "final", "data": final_text}
                        log_event(
                            "chat",
                            "turn_pending",
                            trace_id=trace_id,
                            user_id=user.id,
                            session_id=session.id,
                            tool_name=tool_name,
                            final_chars=len(final_text),
                        )
                        return
                    api_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id"),
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
            else:
                final_text += "\n\n工具调用轮数已达到上限，已停止继续调用。"

            add_message(db, user, session, "assistant", final_text, route=route)
            yield {"type": "final", "data": final_text}
            log_event(
                "chat",
                "turn_final",
                trace_id=trace_id,
                user_id=user.id,
                session_id=session.id,
                source="llm",
                final_chars=len(final_text),
            )
            async for event in self._maybe_switch_context(db, user, session):
                yield event
        except Exception as exc:
            log_event(
                "chat",
                "turn_error",
                trace_id=trace_id,
                user_id=user.id,
                session_id=session.id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            if user_db_message is not None:
                db.delete(user_db_message)
                db.commit()
            yield {"type": "api_error", "data": str(exc), "error_type": type(exc).__name__}

    async def _maybe_switch_context(self, db: Session, user: User, session: ChatSession) -> AsyncIterator[dict[str, Any]]:
        db.refresh(session)
        settings = ensure_user_settings(db, user)
        should_switch, reason = should_switch_context(settings, session)
        if not should_switch:
            return
        yield {"type": "context_switching", "data": {"old_session_id": session.id, "reason": reason}}
        new_session = perform_context_switch(db, user)
        yield {
            "type": "context_switched",
            "data": {
                "old_session_id": session.id,
                "new_session_id": new_session.id,
                "summary_status": "generated" if session.summary else "empty",
            },
        }

    def _build_api_messages(self, system_prompt: str, messages: list[Message]) -> list[dict[str, Any]]:
        api_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for message in messages:
            if message.role not in {"user", "assistant"}:
                continue
            content: Any = message.content
            if message.role == "user" and message.images:
                blocks = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                for image in message.images:
                    if image.get("data"):
                        blocks.append({"type": "image_url", "image_url": {"url": image["data"]}})
                content = blocks
            api_messages.append({"role": message.role, "content": content})
        return api_messages

    async def _stream_openai_once(
        self,
        client: OpenAI,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        tool_names: set[str],
        yield_token: bool,
        forced_tool_name: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        clean_text_parts: list[str] = []
        raw_text_parts: list[str] = []
        tool_call_parts: dict[int, dict[str, Any]] = {}
        text_filter = TextToolCallFilter(tool_names)

        kwargs: dict[str, Any] = {
            "model": self.settings.openai_model,
            "messages": messages,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = (
                {"type": "function", "function": {"name": forced_tool_name}}
                if forced_tool_name
                else "auto"
            )
        if self._is_openrouter and self.settings.openrouter_provider:
            kwargs["extra_body"] = {"provider": {"only": [self.settings.openrouter_provider]}}

        stream = client.chat.completions.create(**kwargs)
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            delta_dict = _safe_model_dump(delta)
            token = delta_dict.get("content") or getattr(delta, "content", None)
            if token:
                raw_text_parts.append(str(token))
                clean_token = text_filter.feed(str(token))
                if clean_token:
                    clean_text_parts.append(clean_token)
                    if yield_token and not forced_tool_name:
                        yield {"type": "token", "data": clean_token}
            for tool_call in _iter_delta_tool_calls(delta, delta_dict):
                index = int(tool_call.get("index", len(tool_call_parts)))
                current = tool_call_parts.setdefault(
                    index,
                    {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                )
                if tool_call.get("id"):
                    current["id"] = str(tool_call["id"])
                fn = tool_call.get("function") or {}
                if fn.get("name"):
                    current["function"]["name"] += str(fn["name"])
                if fn.get("arguments"):
                    current["function"]["arguments"] += str(fn["arguments"])
            await asyncio.sleep(0)

        tail = text_filter.flush()
        if tail:
            clean_text_parts.append(tail)
            if yield_token and not forced_tool_name:
                yield {"type": "token", "data": tail}
        text_calls = text_filter.extracted_calls
        if not text_calls and raw_text_parts:
            text_calls, cleaned_text = extract_text_tool_calls("".join(raw_text_parts), tool_names)
            if text_calls:
                clean_text_parts = [cleaned_text]
        tool_calls = [tool_call_parts[i] for i in sorted(tool_call_parts)]
        for call in tool_calls:
            if not call.get("id"):
                call["id"] = normalize_tool_call(call["function"]["name"], call["function"]["arguments"])["id"]
        tool_calls.extend(text_calls)
        clean_text = "".join(clean_text_parts).strip()
        if yield_token and forced_tool_name and clean_text and not tool_calls:
            yield {"type": "token", "data": clean_text}

        yield {
            "type": "_openai_done",
            "data": {
                "text": clean_text,
                "tool_calls": tool_calls,
            },
        }

    def _parse_forced_tool_arguments(
        self,
        text: str,
        forced_tool_name: str,
        tool_specs: list[ToolSpec],
        *,
        trace_id: str,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any] | None:
        args = parse_json_object_text(text)
        if args is None:
            return None
        spec = next((item for item in tool_specs if item.name == forced_tool_name), None)
        if spec is None:
            return None
        properties = set((spec.parameters.get("properties") or {}).keys())
        required = set(spec.parameters.get("required") or [])
        keys = set(args.keys())
        if properties and not keys.intersection(properties):
            return None
        if required and not required.intersection(keys):
            return None
        log_event(
            "chat",
            "forced_tool_json_arguments_detected",
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            tool_name=forced_tool_name,
            argument_keys=sorted(keys),
        )
        return normalize_tool_call(forced_tool_name, args)

    def _record_tool_event(
        self,
        db: Session,
        user: User,
        session: ChatSession,
        event_type: str,
        data: Any,
    ) -> None:
        if data is None:
            payload: dict[str, Any] = {}
        elif isinstance(data, dict):
            payload = data
        else:
            payload = {"value": data}
        content = self._format_tool_event(event_type, payload)
        add_message(
            db,
            user,
            session,
            "function",
            content,
            raw_content=json.dumps({"type": event_type, "data": payload}, ensure_ascii=False),
            meta={"tool_payload": {"type": event_type, "data": payload}},
        )

    def _format_tool_event(self, event_type: str, payload: dict[str, Any]) -> str:
        if event_type == "tool_call":
            return f"调用工具 `{payload.get('function_name', '')}`"
        if event_type == "tool_result":
            name = payload.get("function_name", "")
            result = payload.get("result", {})
            ok = result.get("ok") if isinstance(result, dict) else None
            return f"工具 `{name}` 返回结果：{'成功' if ok else '失败'}"
        if event_type == "ask_for_info_request":
            title = ((payload.get("payload") or {}).get("meta") or {}).get("title") or "需要补充信息"
            return f"请求用户补充信息：{title}"
        if event_type == "confirmation_request":
            description = ((payload.get("payload") or {}).get("description") or "").strip()
            return f"请求用户确认：{description or '需要确认'}"
        return event_type

    def _pending_tool_message(self, result: dict[str, Any]) -> str:
        event_type = result.get("event_type")
        if event_type == "confirmation_request":
            return "我需要你确认后才能继续，请查看弹出的确认窗口。"
        return "我需要你补充一些信息，请填写弹出的表单后我再继续。"

    def _detect_explicit_tool_request(self, user_message: str, tool_specs: list) -> str | None:
        lowered = user_message.lower()
        for spec in tool_specs:
            if spec.name.lower() in lowered:
                return spec.name
        return None

    async def _fallback_stream(self, user_message: str, route: str, yield_event) -> str:
        return self._fallback_text(user_message, route)

    def _fallback_text(self, user_message: str, route: str) -> str:
        if not user_message.strip():
            return "<bubble>我收到了一条空消息。你可以直接输入想处理的问题。</bubble>"
        return (
            "<bubble>后端已经接收到你的消息，并完成了本地会话写入。</bubble>\n"
            f"<bubble>当前没有配置 `OPENAI_API_KEY`，所以我先用本地回退回复。路由：`{route}`。</bubble>\n\n"
            "你刚才说：\n\n"
            f"> {user_message}\n\n"
            "配置 OpenAI Key 后，这里会切换成真实流式模型回复，并保留 Markdown、LaTeX 与工具调用。"
        )

    @property
    def _is_openrouter(self) -> bool:
        return self.settings.agent_provider == "openrouter" or "openrouter.ai" in self.settings.openai_base_url


def _chunk_text(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


def _safe_model_dump(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            dumped = obj.model_dump(exclude_none=True)
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    return {}


def _iter_delta_tool_calls(delta: Any, delta_dict: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    raw_calls = delta_dict.get("tool_calls")
    if raw_calls is None:
        raw_calls = getattr(delta, "tool_calls", None)
    for raw in raw_calls or []:
        if isinstance(raw, dict):
            calls.append(raw)
            continue
        dumped = _safe_model_dump(raw)
        if dumped:
            calls.append(dumped)

    function_call = delta_dict.get("function_call")
    if function_call is None:
        function_call = getattr(delta, "function_call", None)
    if function_call:
        fn = function_call if isinstance(function_call, dict) else _safe_model_dump(function_call)
        calls.append({"index": 0, "type": "function", "function": fn})
    return calls


agent_orchestrator = AgentOrchestrator()
