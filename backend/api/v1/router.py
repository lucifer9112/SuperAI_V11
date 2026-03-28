"""API router for the stable default runtime."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from backend.config.settings import settings
from backend.api.v1 import chat, memory, system

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key_if_needed(api_key: str | None = Security(_api_key_header)) -> None:
    if settings.server.environment != "production":
        return
    if not api_key or api_key != settings.security.secret_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


api_router = APIRouter(dependencies=[Depends(require_api_key_if_needed)])

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

if _feature_enabled("enable_reflection", "enable_self_improvement", "enable_model_registry", "enable_distributed"):
    from backend.api.v1 import intelligence

    api_router.include_router(intelligence.router, prefix="/intelligence", tags=["Intelligence"])

if _feature_enabled("enable_personality", "enable_parallel_agents"):
    from backend.api.v1 import personality_api

    api_router.include_router(personality_api.router, prefix="/personality", tags=["Personality"])

if _feature_enabled("enable_rlhf"):
    from backend.api.v1 import rlhf_api

    api_router.include_router(rlhf_api.router, prefix="/rlhf", tags=["RLHF"])

if _feature_enabled("enable_tools"):
    from backend.api.v1 import tools_api

    api_router.include_router(tools_api.router, prefix="/tools", tags=["Tools"])

if _feature_enabled("enable_consensus"):
    from backend.api.v1 import consensus_api

    api_router.include_router(consensus_api.router, prefix="/consensus", tags=["Consensus"])

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
