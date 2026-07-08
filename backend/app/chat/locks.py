from __future__ import annotations

import asyncio


_locks: dict[str, asyncio.Lock] = {}


def get_session_lock(user_id: str, session_id: str) -> asyncio.Lock:
    key = f"{user_id}:{session_id}"
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]

