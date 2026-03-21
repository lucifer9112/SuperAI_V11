"""
SuperAI V11 - backend/api/v1/personality_api.py

F11: Personality and identity endpoints.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from backend.app.dependencies import get_orchestrator, get_personality_engine
from backend.models.schemas import APIResponse

router = APIRouter()


@router.get("/profile", response_model=APIResponse, summary="F11: Get AI personality profile")
async def personality_profile(pe=Depends(get_personality_engine)) -> APIResponse:
    if pe is None:
        return APIResponse(success=False, error="PersonalityEngine not loaded")
    return APIResponse(data=pe.get_profile())


@router.get("/session/{session_id}", response_model=APIResponse, summary="F11: Get session emotion and adapted style")
async def session_personality(session_id: str, pe=Depends(get_personality_engine)) -> APIResponse:
    if pe is None:
        return APIResponse(success=False, error="PersonalityEngine not loaded")
    profile = pe._adapter.get_profile(session_id)
    emotion = pe.session_emotion(session_id)
    return APIResponse(
        data={
            "session_id": session_id,
            "emotion": emotion,
            "user_profile": {
                "technical_score": profile.technical_score if profile else 0.5,
                "formality_score": profile.formality_score if profile else 0.5,
                "preferred_depth": profile.preferred_depth if profile else "medium",
                "message_count": profile.message_count if profile else 0,
            }
            if profile
            else None,
        }
    )


class ParallelAgentRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    goal: str
    mode: str = "parallel"
    agents: Optional[List[str]] = None
    session_id: str = ""
    model_name: str = ""


@router.post("/parallel-agents", response_model=APIResponse, summary="F4: Run parallel specialized agents")
async def parallel_agents(req: ParallelAgentRequest, orch=Depends(get_orchestrator)) -> APIResponse:
    result = await orch.run_parallel_agents(
        goal=req.goal,
        mode=req.mode,
        agents=req.agents,
        session_id=req.session_id,
        model_name=req.model_name,
    )
    if hasattr(result, "model_dump"):
        return APIResponse(data=result.model_dump())
    return APIResponse(data={"final_answer": getattr(result, "final_answer", str(result)), "mode": req.mode})
