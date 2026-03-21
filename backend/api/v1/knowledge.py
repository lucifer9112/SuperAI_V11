"""
SuperAI V11 — backend/api/v1/knowledge.py

F5: RAG++ Knowledge endpoints
  POST /api/v1/knowledge/retrieve — manually retrieve web context
  DELETE /api/v1/knowledge/cache  — clear RAG cache
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.app.dependencies import get_rag_engine
from backend.models.schemas import APIResponse

router = APIRouter()


class RetrieveRequest(BaseModel):
    query:    str
    use_cache: bool = True


@router.post("/retrieve", response_model=APIResponse,
             summary="F5: Retrieve live web knowledge for a query")
async def retrieve_knowledge(req: RetrieveRequest,
                              rag=Depends(get_rag_engine)) -> APIResponse:
    if rag is None:
        return APIResponse(success=False, error="RAGEngine not loaded")
    context = await rag.retrieve_context(req.query, use_cache=req.use_cache)
    return APIResponse(data={
        "query":   req.query,
        "context": context,
        "found":   bool(context),
    })


@router.delete("/cache", response_model=APIResponse,
               summary="F5: Clear RAG knowledge cache")
async def clear_cache(rag=Depends(get_rag_engine)) -> APIResponse:
    if rag is None:
        return APIResponse(success=False, error="RAGEngine not loaded")
    rag.clear_cache()
    return APIResponse(data={"cleared": True})
