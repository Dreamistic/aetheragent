from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "app.yaml"
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _deep_get(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


class Settings:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        self.app_name = str(_deep_get(raw, "app.name", "Aether"))
        self.api_prefix = str(_deep_get(raw, "app.api_prefix", "/api"))
        self.default_locale = str(_deep_get(raw, "app.default_locale", "zh-Hans"))
        self.default_theme = str(_deep_get(raw, "app.default_theme", "light"))
        self.database_url = (
            os.getenv("AETHER_DATABASE_URL")
            or os.getenv("VAEAGENT_DATABASE_URL")
            or f"sqlite:///{(DATA_DIR / 'aether.db').as_posix()}"
        )
        self.secret_key = (
            os.getenv("AETHER_SECRET_KEY")
            or os.getenv("VAEAGENT_SECRET_KEY")
            or "dev-secret-change-me"
        )
        self.agent_provider = str(_deep_get(raw, "agent.provider", "openai"))
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", str(_deep_get(raw, "agent.base_url", "")))
        self.openai_model = os.getenv("OPENAI_MODEL", str(_deep_get(raw, "agent.model", "gpt-4.1-mini")))
        self.openrouter_provider = os.getenv(
            "OPENROUTER_PROVIDER",
            str(_deep_get(raw, "agent.openrouter_provider", "")),
        )
        self.openrouter_site_url = os.getenv("OPENROUTER_SITE_URL", "")
        self.openrouter_app_name = os.getenv("OPENROUTER_APP_NAME", self.app_name)
        self.temperature = float(_deep_get(raw, "agent.temperature", 0.7))
        self.max_tokens = int(_deep_get(raw, "agent.max_tokens", 4096))
        self.max_tool_rounds = int(_deep_get(raw, "agent.max_tool_rounds", 4))
        self.access_token_minutes = int(_deep_get(raw, "security.access_token_minutes", 1440))
        self.refresh_token_days = int(_deep_get(raw, "security.refresh_token_days", 30))
        self.context_auto_switch_enabled = bool(
            _deep_get(raw, "sessions.context_auto_switch_enabled", True)
        )
        self.session_timeout_minutes = int(_deep_get(raw, "sessions.session_timeout_minutes", 30))
        self.carried_over_message_count = int(_deep_get(raw, "sessions.carried_over_message_count", 6))
        self.carried_over_expire_threshold = int(
            _deep_get(raw, "sessions.carried_over_expire_threshold", 10)
        )
        self.auto_summary_enabled = bool(_deep_get(raw, "sessions.auto_summary_enabled", True))
        self.auto_switch_min_messages = int(_deep_get(raw, "sessions.auto_switch_min_messages", 24))
        self.default_tool_enabled = dict(_deep_get(raw, "tools.default_enabled", {}) or {})
        self.allow_admin_local_tools = bool(_deep_get(raw, "tools.allow_admin_local_tools", False))
        self.mcp_enabled = bool(_deep_get(raw, "mcp.enabled", True))
        self.mcp_protocol_version = str(_deep_get(raw, "mcp.protocol_version", "2025-06-18"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}
    return Settings(raw)
