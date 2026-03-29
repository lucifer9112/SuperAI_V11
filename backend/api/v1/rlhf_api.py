"""SuperAI V11 - /api/v1/rlhf - RLHF endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from backend.app.dependencies import get_rlhf_pipeline
from backend.models.schemas import APIResponse

router = APIRouter()


class DPORequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    epochs: int = 2


class GRPORequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    prompts: List[str]
    epochs: int = 2


@router.get("/status", response_model=APIResponse, summary="RLHF pipeline status")
async def rlhf_status(rlhf=Depends(get_rlhf_pipeline)):
    if rlhf is None:
        return APIResponse(success=False, error="RLHF pipeline not loaded")
    return APIResponse(data=rlhf.status())


@router.post("/train/dpo", response_model=APIResponse, summary="Trigger DPO training")
async def dpo_train(req: DPORequest, rlhf=Depends(get_rlhf_pipeline)):
    if rlhf is None:
        return APIResponse(success=False, error="RLHF pipeline not loaded")
    if rlhf._dpo._is_running:
        return APIResponse(success=False, error="DPO already running")
    run = await rlhf.run_dpo(req.model_name, req.epochs)
    if run.status != "done":
        return APIResponse(success=False, error=run.metrics.get("message") or run.metrics.get("error") or "DPO failed")
    return APIResponse(data={"run_id": run.run_id, "status": run.status, "metrics": run.metrics})


@router.post("/train/grpo", response_model=APIResponse, summary="Trigger GRPO training")
async def grpo_train(req: GRPORequest, rlhf=Depends(get_rlhf_pipeline)):
    if rlhf is None:
        return APIResponse(success=False, error="RLHF pipeline not loaded")
    run = await rlhf.run_grpo(req.model_name, req.prompts, req.epochs)
    if run.status != "done":
        return APIResponse(success=False, error=run.metrics.get("message") or run.metrics.get("error") or "GRPO failed")
    return APIResponse(data={"run_id": run.run_id, "status": run.status, "metrics": run.metrics})


@router.post("/reward-model/train", response_model=APIResponse, summary="Train neural reward model")
async def train_reward(rlhf=Depends(get_rlhf_pipeline)):
    if rlhf is None:
        return APIResponse(success=False, error="RLHF pipeline not loaded")
    result = await rlhf.train_reward_model()
    return APIResponse(data=result)


@router.post("/score", response_model=APIResponse, summary="Score a response with reward model")
async def score_response(
    prompt: str = Query(...),
    response: str = Query(...),
    rlhf=Depends(get_rlhf_pipeline),
):
    if rlhf is None:
        return APIResponse(success=False, error="RLHF pipeline not loaded")
    score = await rlhf.score_response(prompt, response)
    return APIResponse(data={"prompt": prompt[:80], "score": score})
