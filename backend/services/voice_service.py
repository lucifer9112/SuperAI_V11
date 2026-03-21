"""SuperAI V11 — backend/services/voice_service.py"""
from __future__ import annotations
import asyncio, io, tempfile
from pathlib import Path
from typing import Dict, Optional
from loguru import logger
from backend.config.settings import VoiceSettings
from backend.core.exceptions import VoiceError
from backend.models.schemas import STTResponse


class VoiceService:
    def __init__(self, cfg: VoiceSettings) -> None:
        self.cfg    = cfg
        self._stt   = None
        self._ready = False

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> STTResponse:
        if not self.cfg.enabled:
            return STTResponse(transcript="", language="en", confidence=0.0)
        stt    = await self._get_stt()
        suffix = Path(filename).suffix or ".wav"

        def _run() -> dict:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(audio_bytes); tmp = f.name
            try:
                return stt.transcribe(tmp, language=self.cfg.language or None)
            finally:
                Path(tmp).unlink(missing_ok=True)

        try:
            r = await asyncio.to_thread(_run)
            return STTResponse(transcript=r.get("text","").strip(),
                               language=r.get("language", self.cfg.language),
                               confidence=1.0)
        except Exception as e:
            raise VoiceError(f"STT failed: {e}") from e

    async def synthesize(self, text: str, engine: Optional[str] = None, speed: float = 1.0) -> bytes:
        if not self.cfg.enabled:
            return b""
        eng = engine or self.cfg.tts_engine
        def _run() -> bytes:
            if eng == "gtts":
                from gtts import gTTS
                buf = io.BytesIO(); gTTS(text=text, lang=self.cfg.language).write_to_fp(buf)
                return buf.getvalue()
            import pyttsx3
            engine_obj = pyttsx3.init()
            engine_obj.setProperty("rate",   int(self.cfg.tts_rate * speed))
            engine_obj.setProperty("volume", self.cfg.tts_volume)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            try:
                engine_obj.save_to_file(text, tmp); engine_obj.runAndWait()
                return Path(tmp).read_bytes()
            finally:
                Path(tmp).unlink(missing_ok=True)
        try:
            return await asyncio.to_thread(_run)
        except Exception as e:
            raise VoiceError(f"TTS failed: {e}") from e

    async def get_status(self) -> Dict:
        return {"enabled": self.cfg.enabled, "stt_model": self.cfg.stt_model,
                "tts_engine": self.cfg.tts_engine, "ready": self._ready}

    async def _get_stt(self):
        if self._stt is None:
            def _load():
                import whisper
                return whisper.load_model(self.cfg.stt_model)
            self._stt   = await asyncio.to_thread(_load)
            self._ready = True
        return self._stt
