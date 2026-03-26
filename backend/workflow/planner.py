"""
SuperAI V12 — backend/workflow/planner.py

Plan Writing phase: decomposes a design document into bite-sized tasks.
Each task has description, target files, verification criteria, effort,
and dependencies.

Inspired by Superpowers' writing-plans skill.
"""
from __future__ import annotations

import re
from typing import Any, List, Optional

from loguru import logger

from backend.workflow.models import PlanTask


_PLAN_PROMPT = """You are a technical project manager creating an implementation plan.

Design document:
{design}

Break this into small, concrete engineering tasks. Each task should take 2-5 minutes.
For each task, output EXACTLY this format:

TASK: [short description]
FILES: [comma-separated file paths]
VERIFY: [how to verify this task is done]
DEPENDS: [comma-separated task numbers, or "none"]

Number each task starting from 1. Output at most 15 tasks.
Order tasks so dependencies come first."""


class WorkflowPlanner:
    """Decomposes a design document into concrete implementation tasks."""

    def __init__(self, model_loader: Any = None) -> None:
        self._models = model_loader

    async def create_plan(
        self, design: str, max_tasks: int = 15,
    ) -> List[PlanTask]:
        """Generate ordered tasks from a design document."""
        if self._models is None:
            return self._fallback_plan(design)

        try:
            prompt = _PLAN_PROMPT.format(design=design[:3000])
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt,
                max_tokens=1200, temperature=0.3,
            )
            tasks = self._parse_tasks(answer)
            return tasks[:max_tasks]
        except Exception as e:
            logger.warning("Plan generation failed", error=str(e))
            return self._fallback_plan(design)

    # ── Parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_tasks(text: str) -> List[PlanTask]:
        tasks: List[PlanTask] = []
        current: dict = {}

        for line in text.splitlines():
            stripped = line.strip()
            upper = stripped.upper()

            if upper.startswith("TASK:") or re.match(r"^\d+\.\s*TASK:", upper):
                if current.get("description"):
                    tasks.append(PlanTask(
                        description=current.get("description", ""),
                        target_files=[f.strip() for f in current.get("files", "").split(",") if f.strip()],
                        verification=current.get("verify", ""),
                        dependencies=[d.strip() for d in current.get("depends", "").split(",")
                                      if d.strip() and d.strip().lower() != "none"],
                    ))
                desc = re.sub(r"^\d+\.\s*TASK:\s*", "", stripped, flags=re.IGNORECASE)
                desc = re.sub(r"^TASK:\s*", "", desc, flags=re.IGNORECASE)
                current = {"description": desc}
            elif upper.startswith("FILES:"):
                current["files"] = stripped[6:].strip()
            elif upper.startswith("VERIFY:"):
                current["verify"] = stripped[7:].strip()
            elif upper.startswith("DEPENDS:"):
                current["depends"] = stripped[8:].strip()

        # Flush last task
        if current.get("description"):
            tasks.append(PlanTask(
                description=current.get("description", ""),
                target_files=[f.strip() for f in current.get("files", "").split(",") if f.strip()],
                verification=current.get("verify", ""),
                dependencies=[d.strip() for d in current.get("depends", "").split(",")
                              if d.strip() and d.strip().lower() != "none"],
            ))

        return tasks

    @staticmethod
    def _fallback_plan(design: str) -> List[PlanTask]:
        """Minimal plan when model is unavailable."""
        return [
            PlanTask(description="Set up project structure", verification="Directories exist"),
            PlanTask(description="Implement core logic", verification="Unit tests pass"),
            PlanTask(description="Add API endpoints", verification="Endpoints respond"),
            PlanTask(description="Write tests", verification="All tests green"),
            PlanTask(description="Integration testing", verification="Full flow works"),
        ]
