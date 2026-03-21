"""SuperAI V11 — backend/services/vision_service.py"""
from __future__ import annotations
import asyncio, base64, io
from typing import List, Optional
from loguru import logger
from backend.config.settings import ModelSettings
from backend.core.exceptions import VisionError
from backend.models.schemas import VisionResponse


class VisionService:
    def __init__(self, model_loader, cfg: ModelSettings) -> None:
        self._models = model_loader
        self.cfg     = cfg

    async def analyze(self, image_b64: str, question: str = "Describe this image.",
                      session_id: Optional[str] = None) -> VisionResponse:
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception as e:
            raise VisionError(f"Bad base64: {e}") from e
        try:
            desc = await self._vlm_analyze(image_bytes, question)
        except Exception:
            logger.warning("VLM unavailable, CV fallback")
            desc = await self._cv_analyze(image_bytes)
        return VisionResponse(description=desc)

    async def _vlm_analyze(self, image_bytes: bytes, question: str) -> str:
        model_name = self.cfg.routing.get("vision", "")
        if not model_name:
            raise RuntimeError("No vision model configured")
        def _run() -> str:
            from PIL import Image
            from transformers import pipeline
            pipe   = pipeline("image-to-text", model=model_name)
            img    = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            result = pipe(img, prompt=question, max_new_tokens=512)
            return result[0]["generated_text"]
        return await asyncio.to_thread(_run)

    async def _cv_analyze(self, image_bytes: bytes) -> str:
        def _run() -> str:
            import cv2, numpy as np
            arr = np.frombuffer(image_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return "Could not decode image."
            h, w = img.shape[:2]
            return (f"Image {w}×{h}px. "
                    f"[Install a VLM for full analysis — set models.routing.vision in config.yaml]")
        return await asyncio.to_thread(_run)
