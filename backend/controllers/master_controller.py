"""Central execution controller for the simplified SuperAI V11 pipeline."""

from __future__ import annotations

import time
import uuid
from typing import Any

from loguru import logger

from backend.config.settings import settings
from backend.models.schemas import ChatRequest, ChatResponse, TaskType


class MasterController:
    def __init__(
        self,
        model_loader=None,
        memory_svc=None,
        security_engine=None,
        monitoring_svc=None,
    ) -> None:
        self._models = model_loader
        self._memory = memory_svc
        self._security = security_engine
        self._monitoring = monitoring_svc

        logger.info("MasterController initialized", mode=settings.current_mode)

    @property
    def mode(self) -> str:
        return settings.current_mode

    @property
    def is_minimal(self) -> bool:
        return settings.is_minimal

    async def process(self, req: ChatRequest) -> ChatResponse:
        if self.is_minimal:
            return await self._process_minimal(req)
        return await self._process_advanced(req)

    async def stream(self, req: ChatRequest):
        result = await self.process(req)
        yield result.answer

    async def _process_minimal(self, req: ChatRequest) -> ChatResponse:
        started_at = time.perf_counter()
        session_id = req.session_id or uuid.uuid4().hex[:8]
        response_id = uuid.uuid4().hex[:8]

        if self._security and settings.security.enabled:
            if self._security.validate(req.prompt):
                from backend.core.exceptions import SecurityViolationError

                raise SecurityViolationError("Input blocked by security policy")

        task_type = req.force_task or self._route_task(req.prompt)
        model_name = req.force_model or settings.models.primary
        context = []
        if self._memory and settings.memory.enabled:
            context = await self._memory.get_context(session_id=session_id, prompt=req.prompt)

        prompt = self._build_prompt(req.prompt, task_type, context)
        answer, tokens = await self._run_inference(
            model_name=model_name,
            prompt=prompt,
            max_tokens=req.max_tokens or settings.models.default_max_tokens,
            temperature=req.temperature or settings.models.default_temperature,
        )

        if self._security and settings.security.output_filter:
            answer = self._security.filter_output(answer)

        if self._memory and settings.memory.enabled:
            await self._memory.save_turn(
                session_id=session_id,
                user_text=req.prompt,
                assistant_text=answer,
                response_id=response_id,
            )

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        if self._monitoring:
            self._monitoring.record_request(
                task_type=task_type.value,
                model=model_name,
                latency_ms=latency_ms,
                tokens=tokens,
            )

        return ChatResponse(
            answer=answer,
            session_id=session_id,
            task_type=task_type.value,
            model_used=model_name,
            tokens_used=tokens,
            latency_ms=latency_ms,
            response_id=response_id,
        )

    async def _process_advanced(self, req: ChatRequest) -> ChatResponse:
        logger.info("Advanced mode request routed through master controller", active_features=settings.active_features)
        return await self._process_minimal(req)

    async def _run_inference(
        self,
        *,
        model_name: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, int]:
        if self._models is None:
            return self._fallback_answer(), 0

        try:
            return await self._models.infer(model_name, prompt, max_tokens, temperature)
        except Exception as exc:
            logger.warning("Inference failed, returning controlled fallback", error=str(exc), model=model_name)
            return self._fallback_answer(), 0

    @staticmethod
    def _fallback_answer() -> str:
        return (
            "The API is running, but the local model runtime is not ready. "
            "Install the model dependencies from requirements.txt and ensure the configured model can be downloaded."
        )

    def _route_task(self, prompt: str) -> TaskType:
        prompt_lower = prompt.lower()
        if any(token in prompt_lower for token in ("code", "function", "class ", "import ", "bug", "debug")):
            return TaskType.CODE
        if any(token in prompt_lower for token in ("calculate", "math", "equation", "solve", "integrate")):
            return TaskType.MATH
        if any(token in prompt_lower for token in ("search", "what is", "who is", "where is", "when did")):
            return TaskType.SEARCH
        if any(token in prompt_lower for token in ("document", "pdf", "file", "report", "summary")):
            return TaskType.DOCUMENT
        return TaskType.CHAT

    def _build_prompt(self, prompt: str, task_type: TaskType, context: list[dict[str, Any]]) -> str:
        sections = [settings.personality.system_prompt]

        if task_type == TaskType.CODE:
            sections.append("Task hint: respond with clean, correct, runnable code when appropriate.")
        elif task_type == TaskType.MATH:
            sections.append("Task hint: explain the reasoning clearly and keep the answer concise.")

        if context:
            history = []
            for turn in context[-settings.memory.context_window :]:
                history.append(f"User: {turn.get('user', '')}")
                history.append(f"Assistant: {turn.get('assistant', '')}")
            sections.append("\n".join(history))

        sections.append(f"User: {prompt}")
        sections.append("Assistant:")
        return "\n\n".join(part for part in sections if part.strip())

    def get_status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "is_minimal": self.is_minimal,
            "model_loaded": self._models.loaded_models() if self._models else [],
            "memory_enabled": bool(self._memory) and settings.memory.enabled,
            "security_enabled": settings.security.enabled,
            "features": list(settings.active_features.keys()),
        }
