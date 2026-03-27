"""SuperAI V11 — backend/api/v1/chat.py (Simplified)"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import json

from backend.app.dependencies import get_master_controller, get_memory_service
from backend.models.schemas import APIResponse, ChatRequest

router = APIRouter()


@router.post("/", response_model=APIResponse, summary="Chat")
async def chat(req: ChatRequest, controller=Depends(get_master_controller)) -> APIResponse:
    result = await controller.process(req)
    return APIResponse(data=result.model_dump())


@router.post("/stream", summary="Streaming chat (SSE)")
async def chat_stream(req: ChatRequest, controller=Depends(get_master_controller)) -> StreamingResponse:
    async def _gen():
        async for token in controller.stream(req):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history", response_model=APIResponse, summary="Get session history")
async def get_history(
    session_id: str, limit: int = 20, memory_svc=Depends(get_memory_service)
) -> APIResponse:
    if memory_svc is None:
        return APIResponse(data={"session_id": session_id, "messages": []})
    h = await memory_svc.get_history(session_id=session_id, limit=limit)
    return APIResponse(data={"session_id": session_id, "messages": h})


@router.delete("/history", response_model=APIResponse, summary="Clear session history")
async def clear_history(session_id: str, memory_svc=Depends(get_memory_service)) -> APIResponse:
    if memory_svc is None:
        return APIResponse(data={"cleared": False, "session_id": session_id})
    await memory_svc.clear_history(session_id=session_id)
    return APIResponse(data={"cleared": True, "session_id": session_id})
