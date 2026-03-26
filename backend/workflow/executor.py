"""
SuperAI V12 — backend/workflow/executor.py

Execution phase: dispatches plan tasks to subagents.
After each task, runs 2-stage review (spec compliance + code quality).
Supports checkpoints where user can approve/reject.

Inspired by Superpowers' subagent-driven-development + executing-plans.
"""
from __future__ import annotations

import time
from typing import Any, List, Optional

from loguru import logger

from backend.workflow.models import ExecutionResult, PlanTask, ReviewResult
from backend.workflow.reviewer import WorkflowReviewer


class WorkflowExecutor:
    """Dispatches tasks to agents with post-execution review."""

    def __init__(
        self,
        model_loader: Any = None,
        parallel_executor: Any = None,
    ) -> None:
        self._models = model_loader
        self._parallel = parallel_executor
        self._reviewer = WorkflowReviewer(model_loader)

    async def execute_task(
        self,
        task: PlanTask,
        context: str = "",
        model_name: str = "",
    ) -> ExecutionResult:
        """Execute a single task and review the result."""
        t0 = time.perf_counter()
        task.status = "running"

        # ── Run agent ─────────────────────────────────────────────
        output = ""
        agent_type = "general"

        if self._parallel is not None:
            try:
                from backend.agents.parallel_executor import ExecutionMode
                result = await self._parallel.execute(
                    goal=task.description,
                    mode=ExecutionMode.SINGLE,
                    context=context,
                    model_name=model_name,
                )
                output = result.final_answer
                agent_type = result.winner_agent
            except Exception as e:
                logger.warning("Parallel executor failed", error=str(e))
                output = f"Execution error: {e}"
        elif self._models is not None:
            try:
                prompt = (
                    f"Complete this engineering task:\n\n"
                    f"Task: {task.description}\n"
                    f"Target files: {', '.join(task.target_files) or 'not specified'}\n"
                    f"Verification: {task.verification}\n\n"
                    f"Context:\n{context[:1000]}\n\n"
                    f"Provide the implementation:"
                )
                output, _ = await self._models.infer(
                    model_name=model_name or "",
                    prompt=prompt, max_tokens=600, temperature=0.3,
                )
                agent_type = "direct"
            except Exception as e:
                output = f"Model inference error: {e}"
        else:
            output = f"[Mock execution] Task: {task.description}"
            agent_type = "mock"

        elapsed = (time.perf_counter() - t0) * 1000

        # ── Review ────────────────────────────────────────────────
        review = await self._reviewer.review(
            output=output,
            task_description=task.description,
            verification=task.verification,
        )

        success = review.passed
        task.status = "done" if success else "failed"
        task.result = output[:500]

        return ExecutionResult(
            task_id=task.task_id,
            agent_type=agent_type,
            output=output,
            success=success,
            latency_ms=elapsed,
            review=review,
        )

    async def execute_batch(
        self,
        tasks: List[PlanTask],
        context: str = "",
        model_name: str = "",
        stop_on_critical: bool = True,
    ) -> List[ExecutionResult]:
        """Execute a batch of tasks sequentially with review checkpoints."""
        results: List[ExecutionResult] = []
        accumulated_context = context

        for task in tasks:
            if task.status == "done":
                continue

            result = await self.execute_task(
                task, context=accumulated_context, model_name=model_name,
            )
            results.append(result)

            # Accumulate context from completed tasks
            if result.success:
                accumulated_context += (
                    f"\n[Completed: {task.description[:80]}]: "
                    f"{result.output[:200]}"
                )

            # Stop if critical issue found
            if stop_on_critical and not result.success:
                if result.review and any(
                    i.severity.value == "critical"
                    for i in result.review.issues
                ):
                    logger.warning(
                        "Stopping batch: critical issue",
                        task_id=task.task_id,
                    )
                    break

        return results
