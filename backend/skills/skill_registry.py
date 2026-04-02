"""
SuperAI V11 — backend/skills/skill_registry.py

Registry for loaded skills with auto-activation based on prompt keywords.
Returns enriched system prompts with injected skill instructions.
Includes SkillBundle system for role-based skill grouping.
"""
from __future__ import annotations

import re
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
        """Load skills from directory. Returns count loaded (skips duplicates)."""
        skills = self._loader.load_directory(directory)
        loaded = 0
        for skill in skills:
            if skill.name in self._skills:
                logger.debug("Skill already loaded, skipping duplicate", name=skill.name)
                continue
            self._skills[skill.name] = skill
            loaded += 1
        return loaded

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
        """Find skills that match a prompt using keywords plus semantic overlap."""
        prompt_lower = prompt.lower()
        prompt_tokens = self._tokenize(prompt_lower)
        scored: list[tuple[float, int, str, Skill]] = []

        for skill in self._skills.values():
            if not skill.auto_activate:
                continue
            score, matched = self._score_skill(skill, prompt_lower, prompt_tokens)
            if matched:
                scored.append((score, skill.priority, skill.name, skill))

        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return [skill for _, _, _, skill in scored[:max_skills]]

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

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9][a-z0-9+._-]*", text.lower())

    def _score_skill(self, skill: Skill, prompt_lower: str, prompt_tokens: List[str]) -> tuple[float, bool]:
        prompt_token_set = set(prompt_tokens)
        score = 0.0
        matched = False

        for keyword in skill.trigger_keywords:
            keyword_lower = keyword.lower().strip()
            if not keyword_lower:
                continue
            keyword_tokens = self._tokenize(keyword_lower)

            if " " in keyword_lower:
                if keyword_lower in prompt_lower:
                    score += 4.5 + min(len(keyword_tokens), 3)
                    matched = True
                elif keyword_tokens:
                    overlap = sum(1 for token in keyword_tokens if token in prompt_token_set)
                    if overlap:
                        score += overlap * 1.5
                        matched = True
            else:
                if keyword_lower in prompt_token_set:
                    score += 3.5
                    matched = True
                elif len(keyword_lower) > 3 and keyword_lower in prompt_lower:
                    score += 1.0
                    matched = True

        name_tokens = self._tokenize(skill.name.replace("-", " "))
        for token in name_tokens:
            if token in prompt_token_set:
                score += 3.0
                matched = True

        if skill.name.lower() in prompt_lower:
            score += 4.0
            matched = True

        category_tokens = self._tokenize(skill.category)
        for token in category_tokens:
            if token in prompt_token_set:
                score += 1.5
                matched = True

        description_tokens = {
            token
            for token in self._tokenize(skill.description)
            if len(token) > 3 and token not in {
                "with", "from", "that", "this", "your", "into",
                "best", "practices", "system", "using", "build",
                "development", "engineering", "complete",
            }
        }
        overlap = sum(1 for token in description_tokens if token in prompt_token_set)
        if overlap:
            score += min(overlap, 4) * 0.75
            matched = True

        return score + float(skill.priority), matched

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
