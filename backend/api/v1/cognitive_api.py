"""SuperAI V11 — backend/api/v1/cognitive_api.py — BDI cognitive engine."""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from backend.models.schemas import APIResponse

router = APIRouter()


def _get_engine():
    try:
        from backend.app.dependencies import get_bdi_engine
        eng = get_bdi_engine()
        if eng is not None:
            return eng
    except Exception:
        pass
    from backend.cognitive.bdi_engine import BDICognitiveEngine
    return BDICognitiveEngine()


class BeliefRequest(BaseModel):
    content: str
    source: str = "perception"
    confidence: float = 0.8


class DesireRequest(BaseModel):
    content: str
    priority: float = 0.5
    motivated_by: List[str] = []


class IntentionRequest(BaseModel):
    content: str
    fulfills: str = ""
    supported_by: List[str] = []
    plan_steps: List[str] = []


class PerceiveRequest(BaseModel):
    context: str


class DeliberateRequest(BaseModel):
    request: str


class ExplainRequest(BaseModel):
    intention_id: str


@router.get("/state")
async def get_cognitive_state():
    return _get_engine().state.to_dict()


@router.get("/status", response_model=APIResponse)
async def get_cognitive_status():
    state = _get_engine().state.to_dict()
    summary = state.get("summary", {})
    return APIResponse(
        data={
            "status": "ok",
            "beliefs": summary.get("active_beliefs", 0),
            "desires": summary.get("open_desires", 0),
            "intentions": summary.get("active_intentions", 0),
        }
    )


@router.post("/believe")
async def add_belief(req: BeliefRequest):
    engine = _get_engine()
    b = engine.add_belief(req.content, req.source, req.confidence)
    return {"belief_id": b.belief_id, "content": b.content, "confidence": b.confidence}


@router.post("/desire")
async def add_desire(req: DesireRequest):
    engine = _get_engine()
    d = engine.add_desire(req.content, req.motivated_by, req.priority)
    return {"desire_id": d.desire_id, "content": d.content, "priority": d.priority}


@router.post("/intend")
async def commit_intention(req: IntentionRequest):
    engine = _get_engine()
    i = engine.commit_intention(req.content, req.fulfills, req.supported_by, req.plan_steps)
    return {"intention_id": i.intention_id, "content": i.content, "status": i.status}


@router.post("/perceive")
async def perceive(req: PerceiveRequest):
    engine = _get_engine()
    beliefs = await engine.perceive(req.context)
    return {"new_beliefs": [{"id": b.belief_id, "content": b.content} for b in beliefs]}


@router.post("/deliberate")
async def deliberate(req: DeliberateRequest):
    engine = _get_engine()
    desires = await engine.deliberate(req.request)
    return {"desires": [{"id": d.desire_id, "content": d.content, "priority": d.priority}
                        for d in desires]}


@router.post("/explain")
async def explain_intention(req: ExplainRequest):
    engine = _get_engine()
    return engine.explain_intention(req.intention_id)
