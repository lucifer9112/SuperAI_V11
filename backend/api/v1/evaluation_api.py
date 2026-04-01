"""SuperAI V12 — backend/api/v1/evaluation_api.py — LLM-as-Judge evaluation."""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from backend.models.schemas import APIResponse

router = APIRouter()


def _get_judge():
    try:
        from backend.app.dependencies import get_llm_judge
        j = get_llm_judge()
        if j is not None:
            return j
    except Exception:
        pass
    from backend.evaluation.llm_judge import LLMJudge
    return LLMJudge()


class EvalRequest(BaseModel):
    output: str
    task: str = ""
    reference: str = ""
    criteria: Optional[List[dict]] = None


class PairwiseRequest(BaseModel):
    output_a: str
    output_b: str
    task: str = ""


class CodeEvalRequest(BaseModel):
    code: str
    task: str = ""


@router.get("/status", response_model=APIResponse)
async def evaluation_status():
    judge = _get_judge()
    return APIResponse(
        data={
            "status": "ok",
            "judge_loaded": judge is not None,
            "mode": "llm" if getattr(judge, "_models", None) is not None else "heuristic",
        }
    )


@router.post("/evaluate")
async def evaluate_output(req: EvalRequest):
    judge = _get_judge()
    criteria_objs = None
    if req.criteria:
        from backend.evaluation.llm_judge import JudgeCriterion
        criteria_objs = [JudgeCriterion(
            name=c.get("name", "unnamed"),
            description=c.get("description", ""),
            weight=c.get("weight", 1.0),
        ) for c in req.criteria]

    result = await judge.evaluate(req.output, req.task, req.reference, criteria_objs)
    return {
        "overall_score": result.overall_score,
        "verdict": result.verdict,
        "explanation": result.explanation,
        "criteria": [{"name": c.name, "score": c.score, "weight": c.weight}
                     for c in result.criteria],
    }


@router.post("/pairwise")
async def pairwise_compare(req: PairwiseRequest):
    judge = _get_judge()
    result = await judge.pairwise(req.output_a, req.output_b, req.task)
    return {
        "winner": result.pairwise_winner,
        "verdict": result.verdict,
        "explanation": result.explanation,
    }


@router.post("/evaluate-code")
async def evaluate_code(req: CodeEvalRequest):
    judge = _get_judge()
    result = await judge.evaluate_code(req.code, req.task)
    return {
        "overall_score": result.overall_score,
        "verdict": result.verdict,
        "explanation": result.explanation,
        "criteria": [{"name": c.name, "score": c.score} for c in result.criteria],
    }
