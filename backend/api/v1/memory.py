"""SuperAI V11 — backend/api/v1/memory.py"""
from fastapi import APIRouter, Depends, Query
from backend.app.dependencies import get_memory_service
from backend.models.schemas import APIResponse, MemorySearchRequest, MemoryStoreRequest

router = APIRouter()

@router.post("/search", response_model=APIResponse)
async def search(req: MemorySearchRequest, mem=Depends(get_memory_service)) -> APIResponse:
    return APIResponse(data=(await mem.search(req)).model_dump())

@router.post("/store", response_model=APIResponse)
async def store(req: MemoryStoreRequest, mem=Depends(get_memory_service)) -> APIResponse:
    eid = await mem.store(req)
    return APIResponse(data={"stored": True, "id": eid})

@router.get("/", response_model=APIResponse)
async def list_memories(session_id: str = Query(...), limit: int = 20,
                        mem=Depends(get_memory_service)) -> APIResponse:
    entries = await mem.list(session_id=session_id, limit=limit)
    return APIResponse(data={"entries": entries, "count": len(entries)})

@router.delete("/{entry_id}", response_model=APIResponse)
async def delete_memory(entry_id: str, mem=Depends(get_memory_service)) -> APIResponse:
    deleted = await mem.delete(entry_id)
    return APIResponse(data={"deleted": deleted, "id": entry_id})

@router.post("/{entry_id}/reinforce", response_model=APIResponse,
             summary="Reinforce a memory (increase priority)")
async def reinforce(entry_id: str, boost: float = 0.1,
                    mem=Depends(get_memory_service)) -> APIResponse:
    await mem.reinforce(entry_id, boost)
    return APIResponse(data={"reinforced": True, "id": entry_id, "boost": boost})
