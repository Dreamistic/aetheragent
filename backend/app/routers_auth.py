from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.security import create_token, decode_token, hash_password, verify_password
from backend.app.core.config import get_settings
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.auth import LoginRequest, ProfileUpdateRequest, RefreshRequest, RegisterRequest, TokenResponse
from backend.app.services.serializers import user_to_dict
from backend.app.services.users import ensure_user_settings, find_user_by_login


router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(db: Session, user: User) -> TokenResponse:
    settings = get_settings()
    ensure_user_settings(db, user)
    return TokenResponse(
        access_token=create_token(user.id, "access", timedelta(minutes=settings.access_token_minutes)),
        refresh_token=create_token(user.id, "refresh", timedelta(days=settings.refresh_token_days)),
        user=user_to_dict(user),
    )


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    exists = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="username already exists")
    if payload.email:
        email_exists = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
        if email_exists:
            raise HTTPException(status_code=409, detail="email already exists")
    user = User(username=username, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(db, user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = find_user_by_login(db, payload.username_or_email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username/email or password")
    return _token_response(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")
    user = db.get(User, token_payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="inactive or missing user")
    return _token_response(db, user)


@router.post("/logout")
def logout():
    return {"success": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": user_to_dict(user)}


@router.put("/profile")
def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.username is not None:
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="username is required")
        exists = db.execute(select(User).where(User.username == username, User.id != user.id)).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=409, detail="username already exists")
        user.username = username
    if payload.display_name is not None:
        display_name = payload.display_name.strip()
        user.display_name = display_name or None
    if payload.avatar_data is not None:
        user.avatar_data = payload.avatar_data
    db.commit()
    db.refresh(user)
    return {"user": user_to_dict(user)}


@router.post("/email/verification/request")
def request_email_verification(user: User = Depends(get_current_user)):
    return {
        "success": True,
        "status": "reserved",
        "message": "Email verification delivery is reserved for a future provider integration.",
        "email": user.email,
    }


@router.post("/password/reset/request")
def request_password_reset():
    return {
        "success": True,
        "status": "reserved",
        "message": "Password reset delivery is reserved for a future email provider integration.",
    }
