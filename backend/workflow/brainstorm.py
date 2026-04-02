"""
SuperAI V11 — backend/workflow/brainstorm.py

Brainstorming phase: Socratic design refinement.
Takes a rough idea, generates clarifying questions, and refines into
a structured design document with sections.

Inspired by Superpowers' brainstorming skill.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from backend.workflow.models import BrainstormResult


# ── Prompts ───────────────────────────────────────────────────────

_QUESTION_PROMPT = """You are a senior software architect helping refine a project idea.
The user's rough idea is:

"{idea}"

Generate 3-5 clarifying questions that would help turn this into a concrete design.
Focus on: scope, constraints, target users, key features, and technical requirements.

Format each question on its own line, prefixed with "Q: "."""

_DESIGN_PROMPT = """You are a senior software architect creating a design document.
The project idea is:

"{idea}"

Additional context from user answers:
{context}

Create a structured design document with these sections:
1. **Overview** — what the project does in 2-3 sentences
2. **Key Features** — bullet list of core features
3. **Architecture** — high-level components and how they interact
4. **Data Model** — key entities and relationships
5. **API Design** — main endpoints or interfaces
6. **Risks & Mitigations** — potential issues and how to handle them

Keep each section concise (3-5 bullets or sentences max)."""


class BrainstormEngine:
    """
    Generates clarifying questions and refines ideas into design docs.
    Uses model inference for both steps.
    """

    def __init__(self, model_loader: Any = None) -> None:
        self._models = model_loader

    async def generate_questions(self, idea: str) -> List[str]:
        """Generate clarifying questions for a rough idea."""
        if self._models is None:
            return self._fallback_questions(idea)

        try:
            prompt = _QUESTION_PROMPT.format(idea=idea)
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt, max_tokens=300, temperature=0.7,
            )
            if self._looks_degraded(answer):
                return self._fallback_questions(idea)
            questions = self._parse_questions(answer)
            return questions or self._fallback_questions(idea)
        except Exception as e:
            logger.warning("Brainstorm question generation failed", error=str(e))
            return self._fallback_questions(idea)

    async def refine_design(
        self, idea: str, answers: Optional[Dict[str, str]] = None,
    ) -> BrainstormResult:
        """Refine an idea into a structured design document."""
        context = ""
        if answers:
            context = "\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())

        if self._models is None:
            return self._fallback_design(idea, context)

        try:
            prompt = _DESIGN_PROMPT.format(idea=idea, context=context or "None provided")
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt, max_tokens=800, temperature=0.5,
            )
            if self._looks_degraded(answer):
                return self._fallback_design(idea, context)
            sections = self._parse_sections(answer)
            return BrainstormResult(
                idea=idea,
                questions=list(answers.keys()) if answers else [],
                refined_design=answer,
                sections=sections or self._fallback_design(idea, context).sections,
            )
        except Exception as e:
            logger.warning("Brainstorm design refinement failed", error=str(e))
            return self._fallback_design(idea, context)

    # ── Parsing helpers ───────────────────────────────────────────

    @staticmethod
    def _parse_questions(text: str) -> List[str]:
        questions = []
        for line in text.strip().splitlines():
            line = line.strip()
            if line.startswith("Q:"):
                questions.append(line[2:].strip())
            elif line and line[0].isdigit() and "." in line[:4]:
                questions.append(line.split(".", 1)[-1].strip())
            elif line.startswith("- "):
                questions.append(line[2:].strip())
        return questions[:5] or ["What is the main goal?", "Who are the target users?"]

    @staticmethod
    def _parse_sections(text: str) -> List[Dict[str, str]]:
        sections = []
        current_title = ""
        current_body: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("##") or (stripped.startswith("**") and stripped.endswith("**")):
                if current_title:
                    sections.append({"title": current_title, "body": "\n".join(current_body).strip()})
                current_title = stripped.strip("#* ").strip()
                current_body = []
            else:
                current_body.append(line)
        if current_title:
            sections.append({"title": current_title, "body": "\n".join(current_body).strip()})
        return sections

    # ── Fallbacks (no model) ──────────────────────────────────────

    @staticmethod
    def _fallback_questions(idea: str) -> List[str]:
        return [
            "What is the primary goal of this project?",
            "Who are the target users?",
            "What are the must-have features for v1?",
            "Are there specific technology constraints?",
            "What is the expected scale (users/data)?",
        ]

    @staticmethod
    def _fallback_design(idea: str, context: str) -> BrainstormResult:
        return BrainstormResult(
            idea=idea,
            questions=[],
            refined_design=(
                f"## Overview\n{idea}\n\n"
                f"## Key Features\n- Core user workflow\n- Clear API surface\n- Testable implementation\n\n"
                f"## Architecture\n- Frontend client\n- FastAPI backend\n- Shared data storage\n\n"
                f"## Context\n{context or 'No additional context provided.'}"
            ),
            sections=[
                {"title": "Overview", "body": idea},
                {"title": "Key Features", "body": "Core user workflow\nClear API surface\nTestable implementation"},
                {"title": "Architecture", "body": "Frontend client\nFastAPI backend\nShared data storage"},
            ],
        )

    @staticmethod
    def _looks_degraded(text: str) -> bool:
        lowered = text.lower()
        return "degraded model mode" in lowered or "server is healthy" in lowered
