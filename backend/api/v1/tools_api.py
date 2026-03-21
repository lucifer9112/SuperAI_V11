"""SuperAI V11 — /api/v1/tools — Tool Calling endpoints (Step 2)"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from backend.app.dependencies import get_tool_engine
from backend.models.schemas import APIResponse

router = APIRouter()

class ToolCallRequest(BaseModel):
    prompt:          str
    autonomy_level:  int = 2
    max_tools:       int = 3

class ToolExecuteRequest(BaseModel):
    tool_name:  str
    arguments:  dict = {}

@router.get("/list", response_model=APIResponse, summary="List all available tools")
async def list_tools(category: Optional[str] = None, te=Depends(get_tool_engine)):
    if te is None: return APIResponse(success=False, error="ToolEngine not loaded")
    tools = te._reg.list_tools(category=category)
    return APIResponse(data={"tools":[{"name":t.name,"description":t.description,
        "category":t.category,"safe":t.safe} for t in tools],"count":len(tools)})

@router.post("/call", response_model=APIResponse, summary="Process prompt through tool calling")
async def tool_call(req: ToolCallRequest, te=Depends(get_tool_engine)):
    if te is None: return APIResponse(success=False, error="ToolEngine not loaded")
    result = await te.process(req.prompt, req.autonomy_level, req.max_tools)
    return APIResponse(data={"tools_used":result.tools_used,
        "enriched_prompt":result.enriched_prompt[:500],
        "tool_results":[{"tool":r.tool_name,"success":r.success,
            "output":r.output[:300],"ms":r.exec_ms} for r in result.tool_results],
        "total_ms":result.total_ms})

@router.post("/execute", response_model=APIResponse, summary="Execute a specific tool directly")
async def execute_tool(req: ToolExecuteRequest, te=Depends(get_tool_engine)):
    if te is None: return APIResponse(success=False, error="ToolEngine not loaded")
    result = await te._executor.execute(req.tool_name, req.arguments)
    return APIResponse(data={"tool":result.tool_name,"success":result.success,
        "output":result.output,"error":result.error,"ms":result.exec_ms})
