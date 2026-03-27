"""API router for the stable default runtime."""

from __future__ import annotations

from fastapi import APIRouter

from backend.config.settings import settings
from backend.api.v1 import chat, memory, system

api_router = APIRouter()

api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(memory.router, prefix="/memory", tags=["Memory"])


def _feature_enabled(*flags: str) -> bool:
    return any(settings.active_features.get(flag, False) for flag in flags)


if _feature_enabled("enable_agent", "enable_parallel_agents"):
    from backend.api.v1 import agents

    api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])

if _feature_enabled("enable_voice"):
    from backend.api.v1 import voice

    api_router.include_router(voice.router, prefix="/voice", tags=["Voice"])

if _feature_enabled("enable_vision", "enable_multimodal"):
    from backend.api.v1 import vision

    api_router.include_router(vision.router, prefix="/vision", tags=["Vision"])

if _feature_enabled("enable_context"):
    from backend.api.v1 import files

    api_router.include_router(files.router, prefix="/files", tags=["Files"])

if _feature_enabled("enable_code_review", "enable_debugging"):
    from backend.api.v1 import code

    api_router.include_router(code.router, prefix="/code", tags=["Code"])

if _feature_enabled("enable_feedback", "enable_rlhf"):
    from backend.api.v1 import feedback

    api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])

if _feature_enabled("enable_workflow"):
    from backend.api.v1 import workflow_api

    api_router.include_router(workflow_api.router, prefix="/workflow", tags=["Workflow"])

if _feature_enabled("enable_skills"):
    from backend.api.v1 import skills_api

    api_router.include_router(skills_api.router, prefix="/skills", tags=["Skills"])

if _feature_enabled("enable_cognitive"):
    from backend.api.v1 import cognitive_api

    api_router.include_router(cognitive_api.router, prefix="/cognitive", tags=["Cognitive"])

if _feature_enabled("enable_judge"):
    from backend.api.v1 import evaluation_api

    api_router.include_router(evaluation_api.router, prefix="/evaluation", tags=["Evaluation"])
