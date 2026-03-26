"""
SuperAI V12 — backend/skills/skill_registry.py

Registry for loaded skills with auto-activation based on prompt keywords.
Returns enriched system prompts with injected skill instructions.
Includes SkillBundle system for role-based skill grouping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from loguru import logger

from backend.skills.skill_loader import Skill, SkillLoader


# ── Bundle System ─────────────────────────────────────────────────

@dataclass
class SkillBundle:
    """A curated group of skills for a specific role or goal."""
    name: str
    description: str
    skill_names: List[str]
    icon: str = "📦"

    def to_dict(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "icon": self.icon, "skills": self.skill_names,
            "count": len(self.skill_names),
        }


DEFAULT_BUNDLES: List[SkillBundle] = [
    SkillBundle(
        name="web-dev",
        description="Full-stack web development — frontend, API, testing, deployment",
        icon="🌐",
        skill_names=[
            "frontend-design", "react-patterns", "api-design-principles",
            "python-patterns", "typescript-expert", "testing-patterns",
            "lint-and-validate", "debugging-strategies",
        ],
    ),
    SkillBundle(
        name="security",
        description="Security audit and hardening — OWASP, vulnerability scanning, API security",
        icon="🔒",
        skill_names=[
            "security-auditor", "vulnerability-scanner", "api-security",
            "code-review", "testing-patterns",
        ],
    ),
    SkillBundle(
        name="ai-builder",
        description="AI/ML agent building — RAG, prompt engineering, multi-agent, context",
        icon="🤖",
        skill_names=[
            "rag-engineer", "prompt-engineer", "langgraph",
            "multi-agent-patterns", "memory-systems", "context-fundamentals",
            "context-compression", "bdi-mental-states",
        ],
    ),
    SkillBundle(
        name="full-stack",
        description="Complete full-stack — planning, coding, testing, review, deployment",
        icon="🚀",
        skill_names=[
            "brainstorming", "writing-plans", "architecture",
            "python-patterns", "frontend-design", "api-design-principles",
            "testing-patterns", "debugging-strategies", "code-review",
            "docker-expert", "create-pr",
        ],
    ),
    SkillBundle(
        name="devops",
        description="DevOps and infrastructure — Docker, AWS, Vercel, CI/CD, monitoring",
        icon="⚙️",
        skill_names=[
            "docker-expert", "aws-serverless", "vercel-deployment",
            "workflow-automation", "lint-and-validate",
        ],
    ),
    SkillBundle(
        name="context-engineer",
        description="Context engineering mastery — optimization, compression, degradation, evaluation",
        icon="🧠",
        skill_names=[
            "context-fundamentals", "context-degradation", "context-compression",
            "context-optimization", "evaluation", "advanced-evaluation",
            "memory-systems", "tool-design",
        ],
    ),
]


class SkillRegistry:
    """
    Stores loaded skills and auto-selects relevant ones for a prompt.
    Used by the chat pipeline to enrich system prompts.
    Includes bundle support for role-based skill grouping.
    """

    def __init__(self, skills_dir: str = "", auto_load: bool = True) -> None:
        self._skills: Dict[str, Skill] = {}
        self._bundles: Dict[str, SkillBundle] = {}
        self._active_bundle: Optional[str] = None
        self._loader = SkillLoader()
        if skills_dir and auto_load:
            self.load(skills_dir)
        # Register default bundles
        for bundle in DEFAULT_BUNDLES:
            self._bundles[bundle.name] = bundle

    def load(self, directory: str) -> int:
        """Load skills from directory. Returns count loaded."""
        skills = self._loader.load_directory(directory)
        for skill in skills:
            self._skills[skill.name] = skill
        return len(skills)

    def register(self, skill: Skill) -> None:
        """Manually register a skill."""
        self._skills[skill.name] = skill
        logger.debug("Skill registered", name=skill.name)

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_all(self) -> List[Skill]:
        return sorted(self._skills.values(), key=lambda s: -s.priority)

    def list_by_category(self, category: str) -> List[Skill]:
        return [s for s in self._skills.values() if s.category == category]

    # ── Auto-activation ───────────────────────────────────────────

    def match(self, prompt: str, max_skills: int = 3) -> List[Skill]:
        """Find skills that match a prompt based on trigger keywords."""
        prompt_lower = prompt.lower()
        scored: list[tuple[int, Skill]] = []

        for skill in self._skills.values():
            if not skill.auto_activate:
                continue
            score = 0
            for keyword in skill.trigger_keywords:
                if keyword.lower() in prompt_lower:
                    score += 1
            if score > 0:
                scored.append((score + skill.priority, skill))

        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:max_skills]]

    def enrich_prompt(self, system_prompt: str, user_prompt: str, max_skills: int = 3) -> str:
        """Inject matching skill instructions into the system prompt."""
        matched = self.match(user_prompt, max_skills)

        # Also add skills from active bundle
        if self._active_bundle and self._active_bundle in self._bundles:
            bundle = self._bundles[self._active_bundle]
            for sname in bundle.skill_names:
                skill = self._skills.get(sname)
                if skill and skill not in matched:
                    matched.append(skill)
                    if len(matched) >= max_skills + 2:  # allow 2 extra from bundle
                        break

        if not matched:
            return system_prompt

        skill_block = "\n\n--- Active Skills ---\n"
        for skill in matched:
            skill_block += f"\n### {skill.name}\n{skill.content[:500]}\n"
        skill_block += "\n--- End Skills ---\n"

        return system_prompt + skill_block

    # ── Bundle Management ─────────────────────────────────────────

    def register_bundle(self, bundle: SkillBundle) -> None:
        self._bundles[bundle.name] = bundle

    def get_bundle(self, name: str) -> Optional[SkillBundle]:
        return self._bundles.get(name)

    def list_bundles(self) -> List[SkillBundle]:
        return list(self._bundles.values())

    def activate_bundle(self, name: str) -> Optional[SkillBundle]:
        """Activate a bundle — its skills get priority in prompt enrichment."""
        bundle = self._bundles.get(name)
        if bundle:
            self._active_bundle = name
            logger.info("Bundle activated", bundle=name, skills=len(bundle.skill_names))
        return bundle

    def deactivate_bundle(self) -> None:
        self._active_bundle = None

    def get_active_bundle(self) -> Optional[SkillBundle]:
        if self._active_bundle:
            return self._bundles.get(self._active_bundle)
        return None

    def get_bundle_skills(self, name: str) -> List[Skill]:
        """Get loaded Skill objects for a bundle."""
        bundle = self._bundles.get(name)
        if not bundle:
            return []
        return [self._skills[sn] for sn in bundle.skill_names if sn in self._skills]

    # ── Skill creation ────────────────────────────────────────────

    def create_skill(
        self,
        directory: str,
        name: str,
        description: str,
        triggers: List[str],
        content: str,
        category: str = "custom",
    ) -> Skill:
        """Create a new skill file and register it."""
        path = self._loader.create_skill_file(
            directory, name, description, triggers, content, category,
        )
        skill = Skill(
            name=name,
            description=description,
            trigger_keywords=triggers,
            category=category,
            content=content,
            source_path=path,
        )
        self.register(skill)
        return skill

