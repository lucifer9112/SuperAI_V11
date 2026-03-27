"""SuperAI V11 — backend/api/v1/memory.py (Simplified)"""

from fastapi import APIRouter, Depends, Query
from backend.app.dependencies import get_memory_service
from backend.models.schemas import APIResponse, MemorySearchRequest, MemoryStoreRequest

router = APIRouter()


@router.post("/search", response_model=APIResponse)
async def search(req: MemorySearchRequest, mem=Depends(get_memory_service)) -> APIResponse:
    if mem is None:
        return APIResponse(data={"query": req.query, "entries": [], "total_found": 0})
    return APIResponse(data=(await mem.search(req)).model_dump())


@router.post("/store", response_model=APIResponse)
async def store(req: MemoryStoreRequest, mem=Depends(get_memory_service)) -> APIResponse:
    if mem is None:
        return APIResponse(data={"stored": False, "id": None})
    eid = await mem.store(req)
    return APIResponse(data={"stored": True, "id": eid})


@router.get("/", response_model=APIResponse)
async def list_memories(
    session_id: str = Query(...), limit: int = 20, mem=Depends(get_memory_service)
) -> APIResponse:
    if mem is None:
        return APIResponse(data={"entries": [], "count": 0})
    entries = await mem.list(session_id=session_id, limit=limit)
    return APIResponse(data={"entries": entries, "count": len(entries)})


@router.delete("/{entry_id}", response_model=APIResponse)
async def delete_memory(entry_id: str, mem=Depends(get_memory_service)) -> APIResponse:
    if mem is None:
        return APIResponse(data={"deleted": False, "id": entry_id})
    deleted = await mem.delete(entry_id)
    return APIResponse(data={"deleted": deleted, "id": entry_id})


@router.post("/{entry_id}/reinforce", response_model=APIResponse)
async def reinforce(entry_id: str, boost: float = 0.1, mem=Depends(get_memory_service)) -> APIResponse:
    if mem is None:
        return APIResponse(data={"reinforced": False, "id": entry_id, "boost": boost})
    await mem.reinforce(entry_id, boost)
    return APIResponse(data={"reinforced": True, "id": entry_id, "boost": boost})
