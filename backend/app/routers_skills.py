from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth.dependencies import get_current_user
from backend.app.db.models import User
from backend.app.services.skills import get_skill, list_skills, skill_to_dict


router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
def skills(_: User = Depends(get_current_user)):
    return {"skills": [skill_to_dict(skill) for skill in list_skills()]}


@router.get("/{skill_id}")
def skill_detail(skill_id: str, _: User = Depends(get_current_user)):
    skill = get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return {"skill": skill_to_dict(skill, include_content=True)}
