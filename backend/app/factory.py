"""SuperAI V11 — backend/app/factory.py"""
from __future__ import annotations
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from backend.config.settings import settings
from backend.core.exceptions import SuperAIError
from backend.core.logging import setup_logging
from backend.app.dependencies import container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("SuperAI V11 starting…")
    await container.startup()
    yield
    logger.info("SuperAI V11 shutting down…")
    await container.shutdown()


async def _domain_error(req: Request, exc: SuperAIError) -> JSONResponse:
    logger.warning("Domain error", path=req.url.path, code=exc.error_code)
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict(), headers=exc.headers)

async def _unhandled(req: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", path=req.url.path)
    return JSONResponse(status_code=500, content={"error":"INTERNAL_ERROR","message":"Unexpected error."})

async def _timing(req: Request, call_next):
    t0 = time.perf_counter()
    r  = await call_next(req)
    r.headers["X-Process-Time-Ms"] = str(round((time.perf_counter()-t0)*1000, 2))
    return r


def create_app() -> FastAPI:
    app = FastAPI(
        title       = f"SuperAI V{settings.personality.version} API",
        description = "Next-Generation AGI-Approaching AI Platform",
        version     = settings.personality.version,
        docs_url    = "/docs",
        redoc_url   = "/redoc",
        lifespan    = lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )
    app.middleware("http")(_timing)
    app.add_exception_handler(SuperAIError, _domain_error)  # type: ignore
    app.add_exception_handler(Exception, _unhandled)

    from backend.api.v1.router import api_router
    from backend.api.ws.chat_ws import ws_router
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(ws_router,  prefix="/ws")

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok", "version": settings.personality.version,
                "name": settings.personality.name, "platform": "SuperAI V11"}

    return app
