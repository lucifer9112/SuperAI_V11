"""SuperAI V11 - backend/services/vision_service.py"""
from __future__ import annotations

import asyncio
import base64
import io
from typing import Optional

from loguru import logger

from backend.config.settings import ModelSettings
from backend.core.exceptions import VisionError
from backend.models.schemas import VisionResponse


class VisionService:
    def __init__(self, model_loader, cfg: ModelSettings) -> None:
        self._models = model_loader
        self.cfg = cfg

    async def analyze(
        self,
        image_b64: str,
        question: str = "Describe this image.",
        session_id: Optional[str] = None,
    ) -> VisionResponse:
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception as exc:
            raise VisionError(f"Bad base64: {exc}") from exc

        try:
            description = await self._vlm_analyze(image_bytes, question)
        except Exception as exc:
            logger.warning("VLM unavailable, using degraded vision fallback", error=str(exc))
            description = await self._fallback_analyze(image_bytes, question)
        return VisionResponse(description=description)

    async def _vlm_analyze(self, image_bytes: bytes, question: str) -> str:
        model_name = self.cfg.routing.get("vision", "")
        if not model_name:
            raise RuntimeError("No vision model configured")

        def _run() -> str:
            from PIL import Image
            from transformers import pipeline

            pipe = pipeline("image-to-text", model=model_name)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            result = pipe(image, prompt=question, max_new_tokens=256)
            return result[0]["generated_text"]

        return await asyncio.wait_for(asyncio.to_thread(_run), timeout=20)

    async def _fallback_analyze(self, image_bytes: bytes, question: str) -> str:
        def _run() -> str:
            try:
                from PIL import Image

                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                width, height = image.size
                return (
                    f"Image received successfully ({width}x{height}px). "
                    f"Question noted: {question}. Rich vision analysis is unavailable in this environment, "
                    "so this is a metadata-only fallback."
                )
            except Exception as exc:
                return (
                    f"Image received ({len(image_bytes)} bytes), but image decoding is limited in this environment. "
                    f"Question noted: {question}. Fallback reason: {exc}"
                )

        return await asyncio.to_thread(_run)
