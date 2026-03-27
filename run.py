#!/usr/bin/env python3
"""Single entry point for the simplified SuperAI V11 backend."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SuperAI V11 backend.")
    parser.add_argument("--mode", choices=["minimal", "advanced"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--workers", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode:
        os.environ["SUPERAI_MODE"] = args.mode
    if args.host:
        os.environ["SERVER__HOST"] = args.host
    if args.port is not None:
        os.environ["SERVER__PORT"] = str(args.port)
    if args.workers is not None:
        os.environ["SERVER__WORKERS"] = str(args.workers)

    from backend.config.settings import settings

    host = args.host or settings.server.host
    port = args.port or settings.server.port
    reload_mode = args.reload or settings.server.reload
    workers = 1 if reload_mode else (args.workers or settings.server.workers)
    mode = settings.current_mode

    print(
        "\n".join(
            [
                "",
                "SuperAI V11 backend",
                f"  mode    : {mode}",
                f"  host    : {host}",
                f"  port    : {port}",
                f"  reload  : {reload_mode}",
                f"  workers : {workers}",
                "",
            ]
        )
    )

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload_mode,
        workers=workers,
        log_level=settings.logging.level.lower(),
    )


if __name__ == "__main__":
    main()
