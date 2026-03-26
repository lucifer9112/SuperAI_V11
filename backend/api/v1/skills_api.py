"""SuperAI V12 — backend/api/v1/skills_api.py

REST endpoints for the Skills/Plugin System.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

router = APIRouter()

# ── DI container access ───────────────────────────────────────────
def _get_registry():
    try:
        from backend.app.dependencies import get_skill_registry
        reg = get_skill_registry()
        if reg is not None:
            return reg
    except Exception:
        pass
    from backend.skills.skill_registry import SkillRegistry
    return SkillRegistry(auto_load=False)

# ── Request models ────────────────────────────────────────────────

class MatchReq(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_skills: int = 3

class CreateSkillReq(BaseModel):
    name: str = Field(..., min_length=2)
    description: str = ""
    triggers: List[str] = Field(default_factory=list)
    content: str = ""
    category: str = "custom"

# ── Routes ────────────────────────────────────────────────────────

@router.get("/list")
async def list_skills():
    skills = _get_registry().list_all()
    return {
        "success": True,
        "data": {
            "skills": [s.to_dict() for s in skills],
            "total": len(skills),
        },
    }

@router.get("/{name}")
async def get_skill(name: str):
    skill = _get_registry().get(name)
    if not skill:
        raise HTTPException(404, f"Skill '{name}' not found")
    data = skill.to_dict()
    data["content"] = skill.content[:1000]
    return {"success": True, "data": data}

@router.post("/match")
async def match_skills(req: MatchReq):
    matched = _get_registry().match(req.prompt, req.max_skills)
    return {
        "success": True,
        "data": {
            "matched": [s.to_dict() for s in matched],
            "count": len(matched),
        },
    }

@router.post("/create")
async def create_skill(req: CreateSkillReq):
    try:
        skill = _get_registry().create_skill(
            directory="data/custom_skills",
            name=req.name,
            description=req.description,
            triggers=req.triggers,
            content=req.content,
            category=req.category,
        )
        return {"success": True, "data": skill.to_dict()}
    except Exception as e:
        raise HTTPException(400, str(e))


# ── Bundle Endpoints ──────────────────────────────────────────────

@router.get("/bundles/list")
async def list_bundles():
    bundles = _get_registry().list_bundles()
    return {
        "success": True,
        "data": {
            "bundles": [b.to_dict() for b in bundles],
            "total": len(bundles),
            "active": None,
        },
    }

@router.get("/bundles/{name}")
async def get_bundle(name: str):
    bundle = _get_registry().get_bundle(name)
    if not bundle:
        raise HTTPException(404, f"Bundle '{name}' not found")
    skills = _get_registry().get_bundle_skills(name)
    data = bundle.to_dict()
    data["loaded_skills"] = [s.to_dict() for s in skills]
    data["loaded_count"] = len(skills)
    return {"success": True, "data": data}

@router.post("/bundles/{name}/activate")
async def activate_bundle(name: str):
    bundle = _get_registry().activate_bundle(name)
    if not bundle:
        raise HTTPException(404, f"Bundle '{name}' not found")
    return {
        "success": True,
        "message": f"Bundle '{name}' activated with {len(bundle.skill_names)} skills",
        "data": bundle.to_dict(),
    }

@router.post("/bundles/deactivate")
async def deactivate_bundle():
    _get_registry().deactivate_bundle()
    return {"success": True, "message": "Bundle deactivated"}

