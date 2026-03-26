"""SuperAI V12 — backend/api/v1/debug_api.py

REST endpoints for the Systematic Debugging Engine.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

# ── DI container access ───────────────────────────────────────────
def _get_engine():
    try:
        from backend.app.dependencies import get_debugger
        dbg = get_debugger()
        if dbg is not None:
            return dbg
    except Exception:
        pass
    from backend.debugging.debugger import SystematicDebugger
    return SystematicDebugger()

# ── Request models ────────────────────────────────────────────────

class DebugReq(BaseModel):
    error: str = Field(..., min_length=5, description="Error description or traceback")
    code: str = Field("", description="Relevant code context")

# ── Routes ────────────────────────────────────────────────────────

@router.post("/analyze")
async def full_debug(req: DebugReq):
    report = await _get_engine().full_debug(error=req.error, code=req.code)
    return {"success": True, "data": report.to_dict()}

@router.post("/isolate")
async def isolate_root_cause(req: DebugReq):
    result = await _get_engine().isolate_only(error=req.error, code=req.code)
    return {
        "success": True,
        "data": {
            "phase": result.phase,
            "root_cause": result.analysis[:500],
            "confidence": result.confidence,
            "suggestions": result.suggestions,
        },
    }
