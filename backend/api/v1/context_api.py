"""SuperAI V12 — backend/api/v1/context_api.py — Context compression & optimization."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


def _get_engine():
    try:
        from backend.app.dependencies import get_context_compressor
        eng = get_context_compressor()
        if eng is not None:
            return eng
    except Exception:
        pass
    from backend.context.context_compressor import ContextCompressor
    return ContextCompressor()


class CompressRequest(BaseModel):
    context: str
    target_ratio: float = 0.5
    method: str = "auto"


class DegradationRequest(BaseModel):
    context: str
    max_tokens: int = 3000


class OptimizeRequest(BaseModel):
    segments: List[dict]
    budget: int = 3000


@router.post("/compress")
async def compress_context(req: CompressRequest):
    engine = _get_engine()
    result = await engine.compress(req.context, req.target_ratio, req.method)
    return {
        "original_tokens": result.original_tokens,
        "compressed_tokens": result.compressed_tokens,
        "ratio": result.ratio,
        "method": result.method,
        "quality_scores": result.quality_scores,
    }


@router.post("/degradation")
async def detect_degradation(req: DegradationRequest):
    engine = _get_engine()
    report = engine.detect_degradation(req.context, req.max_tokens)
    return {
        "degradation_detected": report.degradation_detected,
        "severity": report.severity,
        "patterns": report.patterns,
        "recommendations": report.recommendations,
        "utilization": report.context_utilization,
    }


@router.post("/optimize")
async def optimize_context(req: OptimizeRequest):
    from backend.context.context_compressor import ContextSegment
    engine = _get_engine()
    segments = [
        ContextSegment(
            content=s.get("content", ""),
            category=s.get("category", "general"),
            priority=s.get("priority", 0.5),
        )
        for s in req.segments
    ]
    result = engine.build_context(segments, req.budget)
    return {"optimized_context": result, "segment_count": len(segments)}
