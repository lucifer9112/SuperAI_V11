"""SuperAI V11 — backend/api/v1/agents.py"""
from fastapi import APIRouter, Depends, Query
from backend.app.dependencies import get_agent_service, get_coordinator
from backend.models.schemas import APIResponse, AgentRunRequest

router = APIRouter()

@router.post("/run", response_model=APIResponse)
async def run_agent(req: AgentRunRequest, svc=Depends(get_agent_service)):
    return APIResponse(data=(await svc.run(req)).model_dump())

@router.get("/{agent_id}", response_model=APIResponse)
async def agent_status(agent_id: str, svc=Depends(get_agent_service)):
    return APIResponse(data=await svc.get_status(agent_id))

@router.delete("/{agent_id}", response_model=APIResponse)
async def cancel_agent(agent_id: str, svc=Depends(get_agent_service)):
    return APIResponse(data={"cancelled": await svc.cancel(agent_id), "agent_id": agent_id})

@router.get("/", response_model=APIResponse)
async def list_agents(session_id: str = Query(...), svc=Depends(get_agent_service)):
    runs = await svc.list_runs(session_id=session_id)
    return APIResponse(data={"runs": runs, "count": len(runs)})
