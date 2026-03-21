"""SuperAI V11 — backend/api/v1/router.py"""
from fastapi import APIRouter
from backend.api.v1 import (
    chat, agents, memory, voice, vision, files, code,
    system, feedback, intelligence, knowledge, learning,
    security_info, personality_api,
)
# V11 new routers
from backend.api.v1 import rlhf_api, tools_api, consensus_api

api_router = APIRouter()
# V9/V10 core
for mod, prefix, tag in [
    (chat,        "/chat",         "Chat"),
    (agents,      "/agents",       "Agents"),
    (memory,      "/memory",       "Memory"),
    (voice,       "/voice",        "Voice"),
    (vision,      "/vision",       "Vision"),
    (files,       "/files",        "Files"),
    (code,        "/code",         "Code"),
    (system,      "/system",       "System"),
    (feedback,    "/feedback",     "Feedback"),
    (intelligence,"/intelligence", "Intelligence"),
    (knowledge,   "/knowledge",    "Knowledge"),
    (learning,    "/learning",     "Learning"),
    (security_info,"/security",    "Security"),
    (personality_api,"/personality","Personality"),
    # V11 new
    (rlhf_api,    "/rlhf",         "RLHF V11"),
    (tools_api,   "/tools",        "Tools V11"),
    (consensus_api,"/consensus",   "Consensus V11"),
]:
    api_router.include_router(mod.router, prefix=prefix, tags=[tag])
