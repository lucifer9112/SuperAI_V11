"""SuperAI V12 — backend/api/v1/workflow_api.py

REST endpoints for the Agentic Workflow Engine.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

router = APIRouter()

# ── DI container access ───────────────────────────────────────────
def _get_engine():
    try:
        from backend.app.dependencies import get_workflow_engine
        engine = get_workflow_engine()
        if engine is not None:
            return engine
    except Exception:
        pass
    # Fallback for testing / when container not started
    from backend.workflow.engine import WorkflowEngine
    return WorkflowEngine()

# ── Request models ────────────────────────────────────────────────

class WorkflowStartReq(BaseModel):
    idea: str = Field(..., min_length=5, description="Project idea or goal")

class BrainstormReq(BaseModel):
    answers: Optional[Dict[str, str]] = None

class ExecuteReq(BaseModel):
    batch_size: int = Field(3, ge=1, le=10)
    model_name: str = ""

# ── Routes ────────────────────────────────────────────────────────

@router.post("/start")
async def start_workflow(req: WorkflowStartReq):
    try:
        wf = _get_engine().create(req.idea)
        return {"success": True, "data": wf.to_dict()}
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/list")
async def list_workflows():
    return {"success": True, "data": {"workflows": _get_engine().list_all()}}

@router.get("/status/{workflow_id}")
async def workflow_status(workflow_id: str):
    wf = _get_engine().get(workflow_id)
    if not wf:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found")
    return {"success": True, "data": wf.to_dict()}

@router.post("/{workflow_id}/brainstorm")
async def brainstorm(workflow_id: str, req: BrainstormReq = BrainstormReq()):
    try:
        wf = await _get_engine().brainstorm(workflow_id, req.answers)
        data = wf.to_dict()
        if wf.brainstorm:
            data["questions"] = wf.brainstorm.questions
            data["design"] = wf.brainstorm.refined_design[:2000]
            data["sections"] = wf.brainstorm.sections
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{workflow_id}/plan")
async def plan(workflow_id: str):
    try:
        wf = await _get_engine().plan(workflow_id)
        data = wf.to_dict()
        data["tasks"] = [
            {"task_id": t.task_id, "description": t.description,
             "files": t.target_files, "verify": t.verification,
             "status": t.status}
            for t in wf.tasks
        ]
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{workflow_id}/execute")
async def execute(workflow_id: str, req: ExecuteReq = ExecuteReq()):
    try:
        wf = await _get_engine().execute(
            workflow_id, batch_size=req.batch_size, model_name=req.model_name,
        )
        data = wf.to_dict()
        data["latest_executions"] = [
            {"task_id": e.task_id, "agent": e.agent_type,
             "success": e.success, "ms": round(e.latency_ms, 1),
             "output": e.output[:300]}
            for e in wf.executions[-req.batch_size:]
        ]
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{workflow_id}/review")
async def review(workflow_id: str):
    try:
        wf = await _get_engine().review(workflow_id)
        data = wf.to_dict()
        if wf.final_review:
            data["review"] = {
                "passed": wf.final_review.passed,
                "score": wf.final_review.score,
                "summary": wf.final_review.summary,
                "issues": [
                    {"severity": i.severity.value, "description": i.description,
                     "suggestion": i.suggestion}
                    for i in wf.final_review.issues
                ],
            }
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(404, str(e))
