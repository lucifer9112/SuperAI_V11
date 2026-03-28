"""SuperAI V11 — backend/api/v1/files.py"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from backend.app.dependencies import get_orchestrator
from backend.models.schemas import APIResponse

router = APIRouter()

ALLOWED = {".pdf", ".docx", ".xlsx", ".txt", ".py", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

@router.post("/upload", response_model=APIResponse, summary="Upload + process file")
async def upload(file: UploadFile = File(...),
                 question: str = Form("Summarise this document."),
                 session_id: str = Form(None),
                 orch=Depends(get_orchestrator)) -> APIResponse:
    from backend.core.exceptions import BadRequestError

    suffix = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
    if suffix not in ALLOWED:
        raise BadRequestError(f"File type '{suffix}' not supported.", detail={"allowed": list(ALLOWED)})
    size = 0
    chunks = bytearray()
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise BadRequestError(
                "Uploaded file is too large.",
                detail={"max_bytes": MAX_UPLOAD_BYTES},
            )
        chunks.extend(chunk)
    data = bytes(chunks)
    result = await orch.process_file(file.filename or "upload", data, question, session_id)
    return APIResponse(data=result.model_dump())

@router.post("/{file_id}/qa", response_model=APIResponse, summary="Q&A on processed file")
async def file_qa(file_id: str, question: str = Query(...),
                  orch=Depends(get_orchestrator)) -> APIResponse:
    answer = await orch.file_qa(file_id=file_id, question=question)
    return APIResponse(data={"file_id": file_id, "answer": answer})
