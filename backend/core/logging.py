"""SuperAI V11 - backend/core/logging.py - Centralized JSON logging."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from backend.config.settings import settings


def _json_fmt(record: Dict[str, Any]) -> str:
    entry = {
        "ts": record["time"].isoformat(),
        "level": record["level"].name,
        "mod": record["module"],
        "msg": record["message"],
    }
    if record["extra"]:
        entry["extra"] = record["extra"]
    if record["exception"]:
        import traceback

        entry["exc"] = "".join(traceback.format_exception(*record["exception"]))
    return json.dumps(entry)


class _Intercept(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    cfg = settings.logging
    logger.remove()

    log_path = Path(cfg.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    text_format = (
        "<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | "
        "<cyan>{module}</cyan> | <level>{message}</level>"
    )

    if cfg.format == "json":
        logger.add(
            sys.stderr,
            level=cfg.level,
            format="{message}",
            serialize=True,
            colorize=False,
        )
    else:
        logger.add(
            sys.stderr,
            level=cfg.level,
            format=text_format,
            colorize=True,
        )

    file_kwargs = {
        "sink": str(log_path),
        "level": cfg.level,
        "format": "{message}" if cfg.format == "json" else text_format,
        "rotation": cfg.rotation,
        "retention": "30 days",
        "catch": True,
        "serialize": cfg.format == "json",
    }
    try:
        logger.add(enqueue=True, **file_kwargs)
    except (OSError, PermissionError):
        # Some Windows/sandboxed environments block multiprocessing-backed queues.
        logger.add(enqueue=False, **file_kwargs)

    logging.basicConfig(handlers=[_Intercept()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        logging.getLogger(name).handlers = [_Intercept()]

    logger.info("SuperAI V11 logging ready", level=cfg.level, format=cfg.format)
