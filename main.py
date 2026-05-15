"""
Real-Time Chat API — application entry point.

Lifespan:
  startup  → configure logging, start Redis pub/sub subscriber background task
  shutdown → cancel subscriber, close Redis connections

Health check is intentionally kept dependency-free (no DB, no Redis) so that
the orchestrator can detect the process is alive even during partial failures.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.events.redis_subscriber import run_subscriber
from app.managers.redis_manager import close_redis
from app.middleware.rate_limit import limiter
from app.websocket.router import router as ws_router

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup", app=settings.app_name, version=settings.app_version, env=settings.environment)

    # Ensure upload directory exists
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    # Start Redis pub/sub subscriber (bridges cross-process WebSocket messages)
    subscriber_task = asyncio.create_task(run_subscriber(), name="redis_subscriber")

    yield

    logger.info("shutdown_begin")
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass
    await close_redis()
    logger.info("shutdown_complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Production-ready real-time chat backend. "
        "WebSocket-first with Redis pub/sub fan-out for horizontal scaling."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# ── Static files (uploaded images) ───────────────────────────────────────────

Path("uploads/images").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(api_router)
app.include_router(ws_router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}


@app.get("/", tags=["Health"], include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": f"Welcome to {settings.app_name}", "docs": "/docs"}
