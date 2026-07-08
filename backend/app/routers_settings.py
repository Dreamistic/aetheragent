from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.settings import UserSettingsUpdate
from backend.app.services.serializers import settings_to_dict
from backend.app.services.users import ensure_user_settings


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_user_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"settings": settings_to_dict(ensure_user_settings(db, user))}


@router.put("")
def update_user_settings(
    payload: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = ensure_user_settings(db, user)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return {"settings": settings_to_dict(settings)}

