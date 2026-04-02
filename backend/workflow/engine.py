"""
SuperAI V11 — backend/workflow/engine.py

Top-level Workflow Engine orchestrator.
Manages the full pipeline: brainstorm → plan → execute → review → complete.
Tracks active workflows in memory.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from backend.workflow.brainstorm import BrainstormEngine
from backend.workflow.executor import WorkflowExecutor
from backend.workflow.models import (
    IssueSeverity,
    PlanTask,
    ReviewIssue,
    ReviewResult,
    WorkflowPhase,
    WorkflowState,
)
from backend.workflow.planner import WorkflowPlanner
from backend.workflow.reviewer import WorkflowReviewer


class WorkflowEngine:
    """
    Top-level orchestrator for agentic workflows.
    Provides methods for each phase + status queries.
    """

    def __init__(
        self,
        model_loader: Any = None,
        parallel_executor: Any = None,
        max_workflows: int = 5,
    ) -> None:
        self._brainstorm = BrainstormEngine(model_loader)
        self._planner = WorkflowPlanner(model_loader)
        self._executor = WorkflowExecutor(model_loader, parallel_executor)
        self._reviewer = WorkflowReviewer(model_loader)
        self._workflows: Dict[str, WorkflowState] = {}
        self._max_workflows = max_workflows
        logger.info("WorkflowEngine V11 ready")

    # ── Lifecycle ─────────────────────────────────────────────────

    def create(self, idea: str) -> WorkflowState:
        """Create a new workflow from a rough idea."""
        if len(self._workflows) >= self._max_workflows:
            # Remove oldest completed workflow
            completed = [
                wf for wf in self._workflows.values()
                if wf.phase in (WorkflowPhase.COMPLETE, WorkflowPhase.FAILED)
            ]
            if completed:
                oldest = min(completed, key=lambda w: w.created_at)
                del self._workflows[oldest.workflow_id]
            else:
                raise ValueError(
                    f"Max active workflows ({self._max_workflows}) reached"
                )

        wf = WorkflowState(idea=idea)
        self._workflows[wf.workflow_id] = wf
        logger.info("Workflow created", id=wf.workflow_id, idea=idea[:60])
        return wf

    def get(self, workflow_id: str) -> Optional[WorkflowState]:
        return self._workflows.get(workflow_id)

    def list_all(self) -> List[Dict]:
        return [wf.to_dict() for wf in self._workflows.values()]

    # ── Phases ────────────────────────────────────────────────────

    async def brainstorm(
        self,
        workflow_id: str,
        answers: Optional[Dict[str, str]] = None,
    ) -> WorkflowState:
        """Run brainstorming phase — generate questions or refine design."""
        wf = self._require(workflow_id)

        if answers:
            # Refine design with user answers
            result = await self._brainstorm.refine_design(wf.idea, answers)
        else:
            # First pass — generate questions
            questions = await self._brainstorm.generate_questions(wf.idea)
            result = await self._brainstorm.refine_design(wf.idea)
            result.questions = questions

        wf.brainstorm = result
        wf.advance(WorkflowPhase.BRAINSTORM)
        return wf

    async def plan(self, workflow_id: str) -> WorkflowState:
        """Generate implementation plan from brainstorm design."""
        wf = self._require(workflow_id)

        design = ""
        if wf.brainstorm:
            design = wf.brainstorm.refined_design
        if not design:
            design = wf.idea

        tasks = await self._planner.create_plan(design)
        wf.tasks = tasks
        wf.advance(WorkflowPhase.PLAN)
        return wf

    async def execute(
        self,
        workflow_id: str,
        batch_size: int = 3,
        model_name: str = "",
    ) -> WorkflowState:
        """Execute next batch of pending tasks."""
        wf = self._require(workflow_id)

        pending = [t for t in wf.tasks if t.status == "pending"]
        batch = pending[:batch_size]

        if not batch:
            if wf.phase == WorkflowPhase.EXECUTE:
                wf.advance(WorkflowPhase.REVIEW)
            return wf

        context = wf.brainstorm.refined_design if wf.brainstorm else wf.idea
        results = await self._executor.execute_batch(
            tasks=batch, context=context, model_name=model_name,
        )
        wf.executions.extend(results)

        if wf.phase == WorkflowPhase.PLAN:
            wf.advance(WorkflowPhase.EXECUTE)

        if not any(t.status == "pending" for t in wf.tasks) and wf.phase == WorkflowPhase.EXECUTE:
            wf.advance(WorkflowPhase.REVIEW)
        return wf

    async def review(self, workflow_id: str) -> WorkflowState:
        """Run final review on all completed work."""
        wf = self._require(workflow_id)

        if wf.phase == WorkflowPhase.EXECUTE:
            wf.advance(WorkflowPhase.REVIEW)

        pending = [task for task in wf.tasks if task.status == "pending"]
        if pending:
            wf.final_review = ReviewResult(
                passed=False,
                issues=[
                    ReviewIssue(
                        severity=IssueSeverity.WARNING,
                        description=f"{len(pending)} workflow tasks remain pending",
                        suggestion="Execute the remaining tasks before final review",
                    )
                ],
                summary="Workflow review paused until pending tasks are executed",
                score=0.4,
            )
            return wf

        all_output = "\n\n".join(
            f"Task: {e.task_id}\n{e.output[:300]}"
            for e in wf.executions if e.success
        )

        review = await self._reviewer.review(
            output=all_output or "No completed tasks",
            task_description=wf.idea,
            verification="All tasks completed successfully",
        )
        wf.final_review = review

        if review.passed and wf.phase == WorkflowPhase.REVIEW:
            wf.advance(WorkflowPhase.COMPLETE)

        return wf

    # ── Helpers ───────────────────────────────────────────────────

    def _require(self, workflow_id: str) -> WorkflowState:
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found")
        return wf
