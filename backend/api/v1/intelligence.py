"""
SuperAI V11 - backend/api/v1/intelligence.py

API endpoints for reflection, self-improvement, model registry, and task queue.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from backend.app.dependencies import (
    get_model_registry,
    get_reflection_engine,
    get_self_improvement,
    get_task_queue,
)
from backend.models.schemas import APIResponse

router = APIRouter()


class ReflectRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    prompt: str
    answer: str
    task_type: str = "chat"


@router.post("/reflect", response_model=APIResponse, summary="F1: Self-reflect on a response")
async def reflect(req: ReflectRequest, engine=Depends(get_reflection_engine)) -> APIResponse:
    if engine is None:
        return APIResponse(success=False, error="ReflectionEngine not loaded")
    result = await engine.reflect(req.prompt, req.answer, req.task_type)
    return APIResponse(
        data={
            "final_answer": result.final_answer,
            "confidence": result.confidence,
            "was_reflected": result.was_reflected,
            "reflection_notes": result.reflection_notes,
            "rounds": result.rounds,
            "latency_ms": result.latency_ms,
        }
    )


@router.get("/improve/stats", response_model=APIResponse, summary="F6: Self-improvement failure stats")
async def improve_stats(svc=Depends(get_self_improvement)) -> APIResponse:
    if svc is None:
        return APIResponse(success=False, error="SelfImprovementEngine not loaded")
    return APIResponse(data=await svc.get_stats())


@router.get("/improve/suggest", response_model=APIResponse, summary="F6: Get improvement suggestions")
async def improve_suggest(svc=Depends(get_self_improvement)) -> APIResponse:
    if svc is None:
        return APIResponse(data={"suggestions": [], "count": 0})
    suggestions = await svc.suggest_improvements()
    return APIResponse(data={"suggestions": suggestions, "count": len(suggestions)})


class RegisterModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    source: str = "huggingface"
    tasks: List[str] = ["chat"]
    description: str = ""
    base_model: Optional[str] = None


@router.get("/registry", response_model=APIResponse, summary="F7: List registered models")
async def list_registry(task: Optional[str] = None, reg=Depends(get_model_registry)) -> APIResponse:
    if reg is None:
        return APIResponse(success=False, error="ModelRegistry not loaded")
    models = reg.list_models(task=task)
    return APIResponse(
        data={
            "models": [
                {"id": m.model_id, "source": m.source, "tasks": m.tasks, "scores": m.benchmark_scores}
                for m in models
            ],
            "count": len(models),
            "summary": reg.summary(),
        }
    )


@router.post("/registry/register", response_model=APIResponse, summary="F7: Register a new model")
async def register_model(req: RegisterModelRequest, reg=Depends(get_model_registry)) -> APIResponse:
    if reg is None:
        return APIResponse(success=False, error="ModelRegistry not loaded")
    entry = reg.register(req.model_id, req.source, req.tasks, req.description, req.base_model)
    return APIResponse(data={"registered": True, "model_id": entry.model_id})


@router.post("/registry/benchmark", response_model=APIResponse, summary="F7: Benchmark a registered model")
async def benchmark_model(model_id: str, reg=Depends(get_model_registry)) -> APIResponse:
    if reg is None:
        return APIResponse(success=False, error="ModelRegistry not loaded")
    scores = await reg.benchmark(model_id)
    return APIResponse(data={"model_id": model_id, "scores": scores})


@router.get("/task-queue/stats", response_model=APIResponse, summary="F10: Task queue statistics")
async def task_queue_stats(tq=Depends(get_task_queue)) -> APIResponse:
    if tq is None:
        return APIResponse(success=False, error="TaskQueue not loaded")
    return APIResponse(data=tq.stats())
