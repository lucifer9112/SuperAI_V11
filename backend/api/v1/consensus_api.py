"""SuperAI V11 - /api/v1/consensus - Multi-model consensus endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.dependencies import get_consensus_engine
from backend.consensus.consensus_engine import VotingStrategy
from backend.models.schemas import APIResponse

router = APIRouter()


class ConsensusRequest(BaseModel):
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.7
    strategy: str = "auto"


@router.get("/status", response_model=APIResponse, summary="Consensus engine status")
async def consensus_status(ce=Depends(get_consensus_engine)):
    if ce is None:
        return APIResponse(success=False, error="ConsensusEngine not loaded")
    return APIResponse(data=ce.status())


@router.post("/run", response_model=APIResponse, summary="Run multi-model consensus on a prompt")
async def consensus_run(req: ConsensusRequest, ce=Depends(get_consensus_engine)):
    if ce is None:
        return APIResponse(success=False, error="ConsensusEngine not loaded (need >= 2 models in config)")

    try:
        strategy = VotingStrategy(req.strategy)
    except ValueError:
        strategy = VotingStrategy.AUTO

    result = await ce.run(req.prompt, req.max_tokens, req.temperature, strategy=strategy)
    return APIResponse(
        data={
            "final_answer": result.final_answer,
            "winner_model": result.winner_model,
            "strategy": result.strategy,
            "agreement": result.agreement,
            "conflict": result.conflict,
            "latency_ms": result.latency_ms,
            "all_models": [
                {
                    "model": r.model_name,
                    "quality": r.quality,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                }
                for r in result.all_responses
            ],
        }
    )
