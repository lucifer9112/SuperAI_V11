"""
SuperAI V11 — backend/multimodal/fusion_engine.py

FEATURE 9: True Multimodal Fusion

Combines text + image + audio into a unified reasoning prompt.
Strategy: sequential fusion (text describes context, image adds visual info, audio adds spoken intent).
All modalities feed into one LLM call.
"""
from __future__ import annotations

import base64
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from loguru import logger


@dataclass
class MultimodalInput:
    text:         str            = ""
    image_b64:    Optional[str]  = None
    audio_bytes:  Optional[bytes]= None
    session_id:   Optional[str]  = None


@dataclass
class FusedPrompt:
    unified_prompt:  str
    modalities_used: list
    text_weight:     float
    image_desc:      str = ""
    audio_transcript:str = ""


class MultimodalFusionEngine:
    """
    Fuses text + image + audio into a single enriched prompt.
    """

    def __init__(self, cfg, vision_svc, voice_svc) -> None:
        self.cfg        = cfg
        self._vision    = vision_svc
        self._voice     = voice_svc
        self._enabled   = getattr(cfg, "enabled", True)
        self._strategy  = getattr(cfg, "fusion_strategy", "sequential")
        logger.info("MultimodalFusionEngine ready", strategy=self._strategy)

    async def fuse(self, inp: MultimodalInput) -> FusedPrompt:
        """Build a unified multi-modal prompt."""
        if not self._enabled:
            return FusedPrompt(
                unified_prompt=inp.text, modalities_used=["text"],
                text_weight=1.0,
            )

        modalities   = ["text"]
        image_desc   = ""
        audio_transcript = ""

        tasks = []
        if inp.image_b64:
            tasks.append(self._describe_image(inp.image_b64, inp.text))
        else:
            tasks.append(_noop())

        if inp.audio_bytes:
            tasks.append(self._transcribe_audio(inp.audio_bytes))
        else:
            tasks.append(_noop())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        if inp.image_b64 and not isinstance(results[0], Exception):
            image_desc = results[0]
            modalities.append("image")

        if inp.audio_bytes and not isinstance(results[1], Exception):
            audio_transcript = results[1]
            modalities.append("audio")

        unified = self._build_unified_prompt(
            inp.text, image_desc, audio_transcript
        )

        return FusedPrompt(
            unified_prompt   = unified,
            modalities_used  = modalities,
            text_weight      = getattr(self.cfg, "text_weight", 0.6),
            image_desc       = image_desc,
            audio_transcript = audio_transcript,
        )

    def _build_unified_prompt(
        self, text: str, image_desc: str, audio_transcript: str
    ) -> str:
        parts = []
        if text:
            parts.append(f"User text: {text}")
        if image_desc:
            parts.append(f"[Image content: {image_desc}]")
        if audio_transcript:
            parts.append(f"[Spoken input: {audio_transcript}]")
        return "\n".join(parts) or text

    async def _describe_image(self, image_b64: str, question: str) -> str:
        try:
            result = await self._vision.analyze(image_b64, question)
            return result.description
        except Exception as e:
            logger.warning("Image description failed", error=str(e))
            return ""

    async def _transcribe_audio(self, audio_bytes: bytes) -> str:
        try:
            result = await self._voice.transcribe(audio_bytes)
            return result.transcript
        except Exception as e:
            logger.warning("Audio transcription failed", error=str(e))
            return ""


# ── Dummy coroutine helper ────────────────────────────────────────
import asyncio as _asyncio

async def _noop() -> str:
    return ""
