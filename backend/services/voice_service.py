"""SuperAI V11 - backend/services/voice_service.py"""
from __future__ import annotations

import asyncio
import io
import tempfile
import wave
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from backend.config.settings import VoiceSettings
from backend.models.schemas import STTResponse


class VoiceService:
    def __init__(self, cfg: VoiceSettings) -> None:
        self.cfg = cfg
        self._stt = None
        self._ready = False
        self._degraded_reason = ""

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> STTResponse:
        if not self.cfg.enabled:
            return STTResponse(transcript="", language="en", confidence=0.0)

        stt = await self._get_stt()
        if stt is None:
            return STTResponse(transcript="", language=self.cfg.language, confidence=0.0)

        suffix = Path(filename).suffix or ".wav"

        def _run() -> dict:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(audio_bytes)
                temp_name = handle.name
            try:
                return stt.transcribe(temp_name, language=self.cfg.language or None)
            finally:
                Path(temp_name).unlink(missing_ok=True)

        try:
            result = await asyncio.to_thread(_run)
            return STTResponse(
                transcript=result.get("text", "").strip(),
                language=result.get("language", self.cfg.language),
                confidence=1.0,
            )
        except Exception as exc:
            self._degraded_reason = str(exc)
            logger.warning("Voice STT degraded", error=str(exc))
            return STTResponse(transcript="", language=self.cfg.language, confidence=0.0)

    async def synthesize(self, text: str, engine: Optional[str] = None, speed: float = 1.0) -> bytes:
        if not self.cfg.enabled:
            return b""

        selected_engine = (engine or self.cfg.tts_engine or "").lower()

        def _run() -> bytes:
            if selected_engine == "gtts":
                try:
                    from gtts import gTTS

                    buffer = io.BytesIO()
                    gTTS(text=text, lang=self.cfg.language).write_to_fp(buffer)
                    return buffer.getvalue()
                except Exception as exc:
                    self._degraded_reason = str(exc)
                    logger.warning("gTTS unavailable, returning fallback WAV", error=str(exc))
                    return self._fallback_wav()

            try:
                import pyttsx3

                engine_obj = pyttsx3.init()
                engine_obj.setProperty("rate", int(self.cfg.tts_rate * speed))
                engine_obj.setProperty("volume", self.cfg.tts_volume)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                    temp_name = handle.name
                try:
                    engine_obj.save_to_file(text, temp_name)
                    engine_obj.runAndWait()
                    return Path(temp_name).read_bytes()
                finally:
                    Path(temp_name).unlink(missing_ok=True)
            except Exception as exc:
                self._degraded_reason = str(exc)
                logger.warning("pyttsx3 unavailable, returning fallback WAV", error=str(exc))
                return self._fallback_wav()

        try:
            return await asyncio.to_thread(_run)
        except Exception as exc:
            self._degraded_reason = str(exc)
            logger.warning("Voice TTS degraded", error=str(exc))
            return self._fallback_wav()

    async def get_status(self) -> Dict:
        return {
            "enabled": self.cfg.enabled,
            "stt_model": self.cfg.stt_model,
            "tts_engine": self.cfg.tts_engine,
            "ready": self._ready,
            "degraded": bool(self._degraded_reason),
            "reason": self._degraded_reason or None,
        }

    async def _get_stt(self):
        if self._stt is not None:
            return self._stt

        def _load():
            import whisper

            return whisper.load_model(self.cfg.stt_model)

        try:
            self._stt = await asyncio.wait_for(asyncio.to_thread(_load), timeout=20)
            self._ready = True
        except Exception as exc:
            self._degraded_reason = str(exc)
            logger.warning("Whisper unavailable, voice STT running in degraded mode", error=str(exc))
            self._stt = None
        return self._stt

    @staticmethod
    def _fallback_wav(duration_s: float = 0.1, sample_rate: int = 16000) -> bytes:
        """Return a short silent WAV instead of a misleading 440Hz tone."""
        frame_count = max(1, int(duration_s * sample_rate))
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * frame_count)  # silence
        return buffer.getvalue()
