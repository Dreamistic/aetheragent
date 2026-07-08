from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.app_logging import setup_logging
from backend.app.core.config import get_settings
from backend.app.core.config import PROJECT_ROOT
from backend.app.db.init_db import init_db
from backend.app.routers_auth import router as auth_router
from backend.app.routers_chat import router as chat_router
from backend.app.routers_logs import router as logs_router
from backend.app.routers_mcp import router as mcp_router
from backend.app.routers_resources import router as resources_router
from backend.app.routers_skills import router as skills_router
from backend.app.routers_sessions import router as sessions_router
from backend.app.routers_settings import router as settings_router
from backend.app.routers_system import router as system_router
from backend.app.routers_tools import router as tools_router


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db()
        yield

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def no_cache_web_assets(request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith(settings.api_prefix):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    prefix = settings.api_prefix
    app.include_router(system_router, prefix=prefix)
    app.include_router(auth_router, prefix=prefix)
    app.include_router(settings_router, prefix=prefix)
    app.include_router(logs_router, prefix=prefix)
    app.include_router(sessions_router, prefix=prefix)
    app.include_router(tools_router, prefix=prefix)
    app.include_router(mcp_router, prefix=prefix)
    app.include_router(skills_router, prefix=prefix)
    app.include_router(resources_router, prefix=prefix)
    app.include_router(chat_router, prefix=prefix)

    web_build_dir = PROJECT_ROOT / "client" / "build" / "web"
    if web_build_dir.exists():
        app.mount("/", StaticFiles(directory=web_build_dir, html=True), name="web")
    return app


app = create_app()
