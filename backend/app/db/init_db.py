from __future__ import annotations

import base64
import os
from pathlib import Path

from sqlalchemy import inspect, text

from backend.app.db.models import Base
from backend.app.db.session import engine


TEST_AVATAR_PATH = os.getenv("VAEAGENT_TEST_AVATAR_PATH", "")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_user_profile_columns()
    _seed_test_user_avatar()


def _ensure_user_profile_columns() -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("users")}
    statements = []
    if "display_name" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN display_name VARCHAR(120)")
    if "avatar_data" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN avatar_data TEXT")
    if not statements:
        return
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def _seed_test_user_avatar() -> None:
    if not TEST_AVATAR_PATH:
        return
    avatar_path = Path(TEST_AVATAR_PATH)
    if not avatar_path.is_file():
        return
    data = base64.b64encode(avatar_path.read_bytes()).decode("ascii")
    avatar_data = f"data:image/jpeg;base64,{data}"
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE users
                SET avatar_data = COALESCE(NULLIF(avatar_data, ''), :avatar_data),
                    display_name = COALESCE(NULLIF(display_name, ''), username)
                WHERE username = 'test'
                """
            ),
            {"avatar_data": avatar_data},
        )
