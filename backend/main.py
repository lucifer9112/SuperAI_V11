#!/usr/bin/env python3
"""SuperAI V11 — backend/main.py — Single entry point."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import uvicorn
from backend.app.factory    import create_app
from backend.config.settings import settings
app = create_app()
if __name__ == "__main__":
    uvicorn.run("backend.main:app",
                host=settings.server.host, port=settings.server.port,
                reload=settings.server.reload,
                workers=1 if settings.server.reload else settings.server.workers,
                log_level=settings.logging.level.lower())
