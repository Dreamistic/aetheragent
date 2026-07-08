from __future__ import annotations

import json
import logging
import threading
import uuid
from logging.handlers import RotatingFileHandler
from typing import Any

from backend.app.core.config import PROJECT_ROOT


LOG_DIR = PROJECT_ROOT / "logs"
APP_LOG_PATH = LOG_DIR / "vaeagent.log"
EVENT_LOG_PATH = LOG_DIR / "events.jsonl"

_setup_done = False
_event_lock = threading.Lock()


def setup_logging() -> None:
    global _setup_done
    if _setup_done:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("vaeagent")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        APP_LOG_PATH,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    _setup_done = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"vaeagent.{name}")


def new_trace_id(prefix: str = "trace") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def log_event(category: str, event: str, **fields: Any) -> None:
    setup_logging()
    record = {
        "category": category,
        "event": event,
        **_redact(fields),
    }
    line = json.dumps(record, ensure_ascii=False, default=str)
    with _event_lock:
        with EVENT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    logging.getLogger(f"vaeagent.{category}").info("%s %s", event, line)


def read_recent_events(limit: int = 200) -> list[dict[str, Any]]:
    setup_logging()
    if not EVENT_LOG_PATH.exists():
        return []
    limit = max(1, min(limit, 1000))
    lines = EVENT_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError:
            decoded = {"raw": line}
        if isinstance(decoded, dict):
            events.append(decoded)
    return events


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lower = str(key).lower()
            if any(marker in lower for marker in ("password", "token", "secret", "api_key", "authorization")):
                redacted[str(key)] = "***"
            else:
                redacted[str(key)] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
