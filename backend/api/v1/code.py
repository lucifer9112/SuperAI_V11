"""SuperAI V11 — backend/api/v1/code.py"""
from fastapi import APIRouter, Depends
from backend.app.dependencies import get_orchestrator
from backend.models.schemas import APIResponse, CodeRequest

router = APIRouter()

@router.post("/", response_model=APIResponse, summary="Code assistant")
async def code_action(req: CodeRequest, orch=Depends(get_orchestrator)) -> APIResponse:
    result = await orch.code(req)
    return APIResponse(data=result.model_dump())

@router.post("/scan", response_model=APIResponse, summary="Security scan")
async def scan(req: CodeRequest, orch=Depends(get_orchestrator)) -> APIResponse:
    issues = await orch.security_scan(code=req.code, language=req.language)
    return APIResponse(data={"issues": issues, "count": len(issues)})
