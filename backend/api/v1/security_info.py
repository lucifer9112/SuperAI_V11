"""
SuperAI V11 — backend/api/v1/security_info.py

F8: AI Security endpoints
  POST /api/v1/security/assess  — assess a prompt for threats
  GET  /api/v1/security/stats   — security statistics
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.app.dependencies import get_ai_security
from backend.models.schemas import APIResponse

router = APIRouter()


class AssessRequest(BaseModel):
    prompt:     str
    session_id: str = ""


@router.post("/assess", response_model=APIResponse,
             summary="F8: AI threat assessment for a prompt")
async def assess_prompt(req: AssessRequest,
                        sec=Depends(get_ai_security)) -> APIResponse:
    if sec is None:
        return APIResponse(success=False, error="AISecurityEngine not loaded")
    result = await sec.assess(req.prompt, req.session_id)
    return APIResponse(data={
        "is_threat":    result.is_threat,
        "threat_level": result.threat_level,
        "threat_type":  result.threat_type,
        "confidence":   result.confidence,
        "explanation":  result.explanation,
        "blocked":      result.blocked,
    })


@router.get("/stats", response_model=APIResponse,
            summary="F8: AI security statistics")
async def security_stats(sec=Depends(get_ai_security)) -> APIResponse:
    if sec is None:
        return APIResponse(success=False, error="AISecurityEngine not loaded")
    return APIResponse(data=sec.stats())
