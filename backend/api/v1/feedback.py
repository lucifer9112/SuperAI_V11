"""SuperAI V11 — backend/api/v1/feedback.py"""
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_feedback_service
from backend.models.schemas import APIResponse, FeedbackRequest

router = APIRouter()


@router.post("/", response_model=APIResponse)
async def submit(req: FeedbackRequest, svc=Depends(get_feedback_service)):
    if svc is None:
        return APIResponse(success=False, error="Feedback service not loaded")
    return APIResponse(data=(await svc.record(req)).model_dump())


@router.get("/stats", response_model=APIResponse)
async def stats(svc=Depends(get_feedback_service)):
    if svc is None:
        return APIResponse(success=False, error="Feedback service not loaded")
    return APIResponse(data=await svc.get_stats())
