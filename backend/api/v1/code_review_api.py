"""SuperAI V12 — backend/api/v1/code_review_api.py

REST endpoints for the Code Review Engine.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List

router = APIRouter()

# ── DI container access ───────────────────────────────────────────
def _get_engine():
    try:
        from backend.app.dependencies import get_code_review_engine
        eng = get_code_review_engine()
        if eng is not None:
            return eng
    except Exception:
        pass
    from backend.code_review.code_review import CodeReviewEngine
    return CodeReviewEngine()

# ── Request models ────────────────────────────────────────────────

class ReviewReq(BaseModel):
    code: str = Field(..., min_length=1, description="Code to review")
    language: str = ""
    context: str = ""

class SuggestReq(BaseModel):
    code: str = Field(..., min_length=1)
    focus: str = "general improvements"

# ── Routes ────────────────────────────────────────────────────────

@router.post("/review")
async def review_code(req: ReviewReq):
    result = await _get_engine().review(
        code=req.code, language=req.language, context=req.context,
    )
    return {
        "success": True,
        "data": {
            "total_issues": result.total_issues,
            "critical": result.critical,
            "warnings": result.warnings,
            "info": result.info,
            "score": round(result.score, 3),
            "summary": result.summary,
            "issues": [
                {"severity": i.severity, "category": i.category,
                 "description": i.description, "line": i.line,
                 "suggestion": i.suggestion}
                for i in result.issues
            ],
        },
    }

@router.post("/suggest")
async def suggest_improvements(req: SuggestReq):
    suggestions = await _get_engine().suggest(
        code=req.code, focus=req.focus,
    )
    return {
        "success": True,
        "data": {"suggestions": suggestions, "count": len(suggestions)},
    }
