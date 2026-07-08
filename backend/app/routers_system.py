from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.core.config import get_settings


router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name, "model": settings.openai_model}


@router.get("/events/stream")
async def events_stream():
    async def stream() -> AsyncIterator[bytes]:
        yield _sse({"type": "connected", "data": {"timestamp": datetime.now(UTC).isoformat()}})
        while True:
            await asyncio.sleep(30)
            yield _sse({"type": "heartbeat", "data": {"timestamp": datetime.now(UTC).isoformat()}})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


def _sse(event: dict) -> bytes:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")
