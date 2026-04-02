"""SuperAI V11 — backend/app/factory.py (Production-Stable)"""

from __future__ import annotations
import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from loguru import logger

from backend.config.settings import settings
from backend.core.logging import setup_logging
from backend.core.exceptions import SuperAIError
from backend.app.dependencies import container

# Default request timeout in seconds (prevents runaway requests).
REQUEST_TIMEOUT_S = 120


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("SuperAI V11 starting...")
    try:
        await container.startup()
    except Exception as exc:
        logger.exception("Fatal error during startup — running in degraded mode")
        # Don't re-raise: let the app start so /health can report the failure.
    yield
    logger.info("SuperAI V11 shutting down...")
    try:
        await container.shutdown()
    except Exception:
        logger.exception("Error during shutdown")


async def _superai_error_handler(req: Request, exc: SuperAIError) -> JSONResponse:
    """Handle all SuperAIError subclasses with their intended status codes."""
    logger.warning(
        "Request error",
        status=exc.status_code,
        error_code=exc.error_code,
        path=req.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers=exc.headers or {},
    )


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


async def _timeout_middleware(req: Request, call_next):
    """Abort requests that exceed REQUEST_TIMEOUT_S to prevent hangs."""
    try:
        response = await asyncio.wait_for(call_next(req), timeout=REQUEST_TIMEOUT_S)
        return response
    except asyncio.TimeoutError:
        logger.error("Request timed out", path=req.url.path, timeout_s=REQUEST_TIMEOUT_S)
        return JSONResponse(
            status_code=504,
            content={"error": "TIMEOUT", "message": f"Request exceeded {REQUEST_TIMEOUT_S}s timeout."},
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"SuperAI V{settings.personality.version} API",
        description="Production-Ready AI Backend (Stable)",
        version=settings.personality.version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # --- CORS ---
    # When origins is ["*"], credentials MUST be False (browser spec).
    # When origins list specific domains, credentials can be True.
    origins = settings.server.cors_origins
    allow_credentials = origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Middleware ---
    app.middleware("http")(_timing_middleware)

    # --- Exception handlers ---
    # Register SuperAIError FIRST so subclasses get proper status codes.
    app.add_exception_handler(SuperAIError, _superai_error_handler)
    app.add_exception_handler(Exception, _unhandled_error)

    # --- Routers ---
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
