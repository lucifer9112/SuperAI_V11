"""SuperAI V11 - backend/api/v1/voice.py."""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from backend.app.dependencies import get_voice_service
from backend.models.schemas import APIResponse, TTSRequest

router = APIRouter()


@router.post("/tts", summary="Text to speech audio")
async def tts(req: TTSRequest, svc=Depends(get_voice_service)) -> Response:
    audio = await svc.synthesize(req.text, req.engine, req.speed)
    engine = (req.engine or svc.cfg.tts_engine or "").lower()
    is_mp3 = engine == "gtts"
    media_type = "audio/mpeg" if is_mp3 else "audio/wav"
    filename = "response.mp3" if is_mp3 else "response.wav"
    return Response(
        content=audio,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@router.post("/stt", response_model=APIResponse, summary="Audio to transcript")
async def stt(audio: UploadFile = File(...), svc=Depends(get_voice_service)) -> APIResponse:
    data = await audio.read()
    result = await svc.transcribe(data, audio.filename or "audio.wav")
    return APIResponse(data=result.model_dump())


@router.get("/status", response_model=APIResponse)
async def status(svc=Depends(get_voice_service)) -> APIResponse:
    return APIResponse(data=await svc.get_status())
