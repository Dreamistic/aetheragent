from __future__ import annotations

from pathlib import Path

from backend.app.core.config import PROJECT_ROOT
from backend.app.db.models import ChatSession, UserSettings
from backend.app.services.skills import render_skill_docs


PROMPT_ROOT = PROJECT_ROOT / "backend" / "app" / "prompts"
SUPPORTED_LOCALES = {"zh-Hans", "zh-Hant", "en"}


def normalize_locale(locale: str | None) -> str:
    if locale in SUPPORTED_LOCALES:
        return str(locale)
    if locale and locale.lower().startswith("zh-hant"):
        return "zh-Hant"
    if locale and locale.lower().startswith("zh"):
        return "zh-Hans"
    return "en"


def load_base_prompt(locale: str | None) -> str:
    resolved = normalize_locale(locale)
    path: Path = PROMPT_ROOT / resolved / "base.md"
    if not path.exists():
        path = PROMPT_ROOT / "en" / "base.md"
    return path.read_text(encoding="utf-8")


def build_system_prompt(
    settings: UserSettings,
    session: ChatSession,
    tool_descriptions: str,
    route: str | None = None,
) -> str:
    prompt = load_base_prompt(settings.locale)
    blocks = [prompt]
    if session.summary:
        blocks.append(f"<previous_session_summary>\n{session.summary}\n</previous_session_summary>")
    if session.carried_over_context:
        lines = []
        for item in session.carried_over_context:
            role = item.get("role", "user")
            content = item.get("content", "")
            lines.append(f"{role}: {content}")
        blocks.append("<carried_over_context>\n" + "\n".join(lines[-settings.carried_over_message_count :]) + "\n</carried_over_context>")
    if route:
        blocks.append(f"<route>{route}</route>")
    blocks.append(
        "<function_system>\n"
        "<rules>\n"
        "- Use native tool/function calls whenever the provider supports them.\n"
        "- If native tool calls are not emitted, use exactly one <function_calls> XML block as textual fallback.\n"
        "- Never show bare argument JSON to the user as the final answer.\n"
        "- Wait for tool_result before claiming success.\n"
        "</rules>\n"
        "<available_tools>\n"
        + tool_descriptions
        + "\n</available_tools>\n"
        "</function_system>"
    )
    skill_docs = render_skill_docs()
    if skill_docs:
        blocks.append("<available_skills>\n" + skill_docs + "\n</available_skills>")
    return "\n\n".join(blocks)
