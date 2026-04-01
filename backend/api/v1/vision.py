"""SuperAI V11 — backend/api/v1/vision.py"""
import base64
from fastapi import APIRouter, Depends, File, Form, UploadFile

from backend.app.dependencies import get_vision_service
from backend.models.schemas import APIResponse, VisionRequest

router = APIRouter()


@router.post("/analyze", response_model=APIResponse)
async def analyze(req: VisionRequest, svc=Depends(get_vision_service)) -> APIResponse:
    if svc is None:
        return APIResponse(success=False, error="Vision service not loaded")
    result = await svc.analyze(req.image_base64, req.question, req.session_id)
    return APIResponse(data=result.model_dump())


@router.post("/upload", response_model=APIResponse)
async def upload(image: UploadFile = File(...),
                 question: str = Form("Describe this image."),
                 session_id: str = Form(None),
                 svc=Depends(get_vision_service)) -> APIResponse:
    if svc is None:
        return APIResponse(success=False, error="Vision service not loaded")
    data   = await image.read()
    b64    = base64.b64encode(data).decode()
    result = await svc.analyze(b64, question, session_id)
    return APIResponse(data=result.model_dump(),
                       meta={"filename": image.filename, "size_bytes": len(data)})
