from __future__ import annotations

import json
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any


TEXT_TOOL_BLOCK_RE = re.compile(
    r"<(?P<tag>function_calls|tool_calls|tool_call)\b[^>]*>.*?</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
FENCED_TOOL_RE = re.compile(
    r"```(?:json|tool_call|tool_calls|function_calls)\s*(?P<body>[\s\S]*?)```",
    re.IGNORECASE,
)
FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(?P<body>[\s\S]*?)```", re.IGNORECASE)
START_TAG_RE = re.compile(r"<(function_calls|tool_calls|tool_call)\b[^>]*>", re.IGNORECASE)


def normalize_tool_call(name: str, arguments: dict[str, Any] | str | None, call_id: str | None = None) -> dict[str, Any]:
    if isinstance(arguments, str):
        arguments_json = arguments
    else:
        arguments_json = json.dumps(arguments or {}, ensure_ascii=False)
    return {
        "id": call_id or f"call_{uuid.uuid4().hex}",
        "type": "function",
        "function": {"name": name, "arguments": arguments_json},
    }


def extract_text_tool_calls(text: str, tool_names: set[str]) -> tuple[list[dict[str, Any]], str]:
    calls: list[dict[str, Any]] = []
    cleaned = text

    for match in list(TEXT_TOOL_BLOCK_RE.finditer(text)):
        block = match.group(0)
        calls.extend(_parse_tool_block(block, tool_names))
    cleaned = TEXT_TOOL_BLOCK_RE.sub("", cleaned)

    for match in list(FENCED_TOOL_RE.finditer(cleaned)):
        body = match.group("body")
        parsed = _parse_json_tool_payload(body, tool_names)
        if parsed:
            calls.extend(parsed)
            cleaned = cleaned.replace(match.group(0), "")

    return _dedupe_calls(calls), cleaned.strip()


def strip_text_tool_blocks(text: str) -> str:
    cleaned = TEXT_TOOL_BLOCK_RE.sub("", text)
    return cleaned.strip()


def parse_json_object_text(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    fence_match = FENCED_JSON_RE.fullmatch(candidate)
    if fence_match:
        candidate = fence_match.group("body").strip()
    if not candidate.startswith("{") or not candidate.endswith("}"):
        return None
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _parse_tool_block(block: str, tool_names: set[str]) -> list[dict[str, Any]]:
    parsed = _parse_function_calls_xml(block, tool_names)
    if parsed:
        return parsed

    inner = re.sub(r"^<[^>]+>|</[^>]+>$", "", block.strip(), flags=re.DOTALL).strip()
    return _parse_json_tool_payload(inner, tool_names)


def _parse_function_calls_xml(block: str, tool_names: set[str]) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(block)
    except ET.ParseError:
        return []

    calls: list[dict[str, Any]] = []
    nodes = [root] if root.tag.lower() in {"invoke", "tool_call"} else list(root)
    for node in nodes:
        tag = node.tag.lower()
        if tag not in {"invoke", "tool_call", "call"}:
            continue
        name = (
            node.attrib.get("name")
            or node.attrib.get("function")
            or node.attrib.get("tool")
            or (node.findtext("name") if node.find("name") is not None else "")
        )
        name = (name or "").strip()
        if name not in tool_names:
            continue
        args: dict[str, Any] = {}
        arguments_text = node.findtext("arguments")
        if arguments_text:
            try:
                decoded = json.loads(arguments_text)
                if isinstance(decoded, dict):
                    args.update(decoded)
            except json.JSONDecodeError:
                args["value"] = arguments_text
        for param in node.findall(".//parameter"):
            param_name = (param.attrib.get("name") or param.attrib.get("key") or "").strip()
            if not param_name:
                continue
            args[param_name] = _parse_parameter_value(param.text or "")
        calls.append(normalize_tool_call(name, args, node.attrib.get("id")))
    return calls


def _parse_json_tool_payload(payload: str, tool_names: set[str]) -> list[dict[str, Any]]:
    payload = payload.strip()
    if not payload:
        return []
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return []
    return _calls_from_json(decoded, tool_names)


def _calls_from_json(decoded: Any, tool_names: set[str]) -> list[dict[str, Any]]:
    if isinstance(decoded, list):
        calls: list[dict[str, Any]] = []
        for item in decoded:
            calls.extend(_calls_from_json(item, tool_names))
        return calls
    if not isinstance(decoded, dict):
        return []

    if isinstance(decoded.get("tool_calls"), list):
        return _calls_from_json(decoded["tool_calls"], tool_names)
    if isinstance(decoded.get("calls"), list):
        return _calls_from_json(decoded["calls"], tool_names)

    function = decoded.get("function")
    if isinstance(function, dict):
        name = str(function.get("name") or "").strip()
        arguments = function.get("arguments", decoded.get("arguments", {}))
    else:
        name = str(decoded.get("name") or decoded.get("tool") or decoded.get("function_name") or "").strip()
        arguments = decoded.get("arguments", decoded.get("args", {}))

    if name not in tool_names:
        return []
    return [normalize_tool_call(name, arguments, str(decoded.get("id") or "") or None)]


def _parse_parameter_value(value: str) -> Any:
    text = value.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _dedupe_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for call in calls:
        function = call.get("function") or {}
        key = (str(function.get("name") or ""), str(function.get("arguments") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(call)
    return unique


@dataclass
class TextToolCallFilter:
    tool_names: set[str]
    buffer: str = ""
    block: str = ""
    in_block: bool = False
    block_tag: str = ""
    extracted_calls: list[dict[str, Any]] = field(default_factory=list)

    def feed(self, chunk: str) -> str:
        self.buffer += chunk
        return self._drain()

    def flush(self) -> str:
        if self.in_block:
            pending = self.block + self.buffer
            self.block = ""
            self.buffer = ""
            self.in_block = False
            self.block_tag = ""
            return pending
        text = self.buffer
        self.buffer = ""
        return text

    def _drain(self) -> str:
        emitted: list[str] = []
        while True:
            if self.in_block:
                close = f"</{self.block_tag}>"
                lower_buffer = self.buffer.lower()
                end = lower_buffer.find(close)
                if end < 0:
                    self.block += self.buffer
                    self.buffer = ""
                    break
                end_index = end + len(close)
                self.block += self.buffer[:end_index]
                self.extracted_calls.extend(_parse_tool_block(self.block, self.tool_names))
                self.buffer = self.buffer[end_index:]
                self.block = ""
                self.in_block = False
                self.block_tag = ""
                continue

            match = START_TAG_RE.search(self.buffer)
            if match:
                emitted.append(self.buffer[: match.start()])
                self.block_tag = match.group(1).lower()
                self.block = self.buffer[match.start() :]
                self.buffer = ""
                self.in_block = True
                continue

            keep = 32
            if len(self.buffer) > keep:
                emitted.append(self.buffer[:-keep])
                self.buffer = self.buffer[-keep:]
            break
        return "".join(emitted)
