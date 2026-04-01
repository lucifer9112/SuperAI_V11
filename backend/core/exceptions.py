"""SuperAI V11 — backend/core/exceptions.py — Unified exception hierarchy."""
from __future__ import annotations
from typing import Any, Dict, Optional


class SuperAIError(Exception):
    status_code: int = 500
    error_code:  str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: Optional[Any] = None,
                 headers: Optional[Dict[str, str]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail  = detail
        self.headers = headers or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"error": self.error_code, "message": self.message, "detail": self.detail}


class BadRequestError(SuperAIError):
    status_code = 400; error_code = "BAD_REQUEST"

class UnauthorizedError(SuperAIError):
    status_code = 401; error_code = "UNAUTHORIZED"

class ForbiddenError(SuperAIError):
    status_code = 403; error_code = "FORBIDDEN"

class NotFoundError(SuperAIError):
    status_code = 404; error_code = "NOT_FOUND"

class RateLimitError(SuperAIError):
    status_code = 429; error_code = "RATE_LIMITED"

class ModelLoadError(SuperAIError):
    error_code = "MODEL_LOAD_ERROR"

class ModelInferenceError(SuperAIError):
    error_code = "MODEL_INFERENCE_ERROR"

class SecurityViolationError(SuperAIError):
    status_code = 422; error_code = "SECURITY_VIOLATION"

class MemoryServiceError(SuperAIError):
    error_code = "MEMORY_ERROR"

class AgentError(SuperAIError):
    error_code = "AGENT_ERROR"

class VoiceError(SuperAIError):
    error_code = "VOICE_ERROR"

class VisionError(SuperAIError):
    error_code = "VISION_ERROR"

class FileProcessingError(SuperAIError):
    error_code = "FILE_PROCESSING_ERROR"

class FeedbackError(SuperAIError):
    error_code = "FEEDBACK_ERROR"
