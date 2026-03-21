"""
SuperAI V11 — backend/api/v1/learning.py

F2: Continuous Learning endpoints
  GET  /api/v1/learning/status    — pipeline status
  POST /api/v1/learning/collect   — trigger dataset collection now
  POST /api/v1/learning/train     — trigger LoRA training now
"""
from fastapi import APIRouter, Depends, Query
from backend.app.dependencies import get_learning_pipeline
from backend.models.schemas import APIResponse

router = APIRouter()


@router.get("/status", response_model=APIResponse, summary="F2: Learning pipeline status")
async def learning_status(lp=Depends(get_learning_pipeline)) -> APIResponse:
    if lp is None:
        return APIResponse(success=False, error="LearningPipeline not loaded")
    return APIResponse(data=lp.status())


@router.post("/collect", response_model=APIResponse,
             summary="F2: Collect training examples from feedback now")
async def collect_now(lp=Depends(get_learning_pipeline)) -> APIResponse:
    if lp is None:
        return APIResponse(success=False, error="LearningPipeline not loaded")
    n = await lp.collect_now()
    return APIResponse(data={"collected": n, "total": lp._total_collected})


@router.post("/train", response_model=APIResponse,
             summary="F2: Trigger LoRA fine-tuning now (runs in background)")
async def train_now(
    model_name: str = Query("TinyLlama/TinyLlama-1.1B-Chat-v1.0"),
    lp=Depends(get_learning_pipeline),
) -> APIResponse:
    if lp is None:
        return APIResponse(success=False, error="LearningPipeline not loaded")
    if lp.trainer.is_training:
        return APIResponse(success=False, error="Training already in progress")
    checkpoint = await lp.train_now(model_name)
    if checkpoint:
        return APIResponse(data={"started": True, "checkpoint_path": checkpoint})
    return APIResponse(success=False, error="Not enough training examples (need >= 10)")
