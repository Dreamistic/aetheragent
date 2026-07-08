from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.app.core.config import PROJECT_ROOT


SKILLS_DIR = PROJECT_ROOT / "backend" / "skills"


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    content: str
    path: str


def list_skills() -> list[SkillDefinition]:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skills: list[SkillDefinition] = []
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        skill_id = path.parent.name
        name = _extract_heading(content) or skill_id
        description = _extract_description(content)
        skills.append(
            SkillDefinition(
                id=skill_id,
                name=name,
                description=description,
                content=content,
                path=str(path.relative_to(PROJECT_ROOT)),
            )
        )
    return skills


def get_skill(skill_id: str) -> SkillDefinition | None:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "", skill_id)
    if normalized != skill_id:
        return None
    for skill in list_skills():
        if skill.id == skill_id:
            return skill
    return None


def render_skill_docs(max_chars: int = 6000) -> str:
    docs: list[str] = []
    total = 0
    for skill in list_skills():
        block = f"## {skill.name} ({skill.id})\n{skill.content}"
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining <= 200:
                break
            block = block[:remaining] + "\n..."
        docs.append(block)
        total += len(block)
    return "\n\n".join(docs)


def skill_to_dict(skill: SkillDefinition, include_content: bool = False) -> dict:
    data = {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "path": skill.path,
        "loaded": True,
    }
    if include_content:
        data["content"] = skill.content
    return data


def _extract_heading(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.removeprefix("# ").strip()
    return None


def _extract_description(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped[:180]
    return ""
