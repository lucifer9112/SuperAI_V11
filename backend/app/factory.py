"""SuperAI V11 — backend/app/factory.py (Simplified)"""

from __future__ import annotations
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from loguru import logger

from backend.config.settings import settings
from backend.core.logging import setup_logging
from backend.app.dependencies import container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("SuperAI V11 starting...")
    await container.startup()
    yield
    logger.info("SuperAI V11 shutting down...")
    await container.shutdown()


async def _unhandled_error(req: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": str(exc)
            if settings.server.environment == "development"
            else "An unexpected error occurred.",
        },
    )


async def _timing_middleware(req: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(req)
    response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - t0) * 1000, 2))
    return response


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"SuperAI V{settings.personality.version} API",
        description="Production-Ready AI Backend (Simplified & Stable)",
        version=settings.personality.version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=settings.server.cors_origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(_timing_middleware)
    app.exception_handler(Exception)(_unhandled_error)

    from backend.api.v1.router import api_router
    from backend.api.ws.chat_ws import ws_router

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(ws_router, prefix="/ws")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs", status_code=307)

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {
            "status": "ok",
            "version": settings.personality.version,
            "name": settings.personality.name,
            "mode": settings.current_mode,
            "is_minimal": settings.is_minimal,
            "active_features": list(settings.active_features.keys()),
        }

    return app
