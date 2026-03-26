"""
SuperAI V12 — backend/workflow/models.py

Data models for the Agentic Workflow Engine.
Tracks workflow lifecycle: BRAINSTORM → PLAN → EXECUTE → REVIEW → COMPLETE.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enums ─────────────────────────────────────────────────────────

class WorkflowPhase(str, Enum):
    CREATED    = "created"
    BRAINSTORM = "brainstorm"
    PLAN       = "plan"
    EXECUTE    = "execute"
    REVIEW     = "review"
    COMPLETE   = "complete"
    FAILED     = "failed"


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING  = "warning"
    INFO     = "info"


# ── Core Models ───────────────────────────────────────────────────

@dataclass
class BrainstormResult:
    idea: str
    questions: List[str] = field(default_factory=list)
    refined_design: str = ""
    sections: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class PlanTask:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    target_files: List[str] = field(default_factory=list)
    verification: str = ""
    estimated_minutes: int = 5
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"        # pending | running | done | failed
    result: Optional[str] = None


@dataclass
class ReviewIssue:
    severity: IssueSeverity
    description: str
    location: str = ""
    suggestion: str = ""


@dataclass
class ReviewResult:
    passed: bool
    issues: List[ReviewIssue] = field(default_factory=list)
    summary: str = ""
    score: float = 0.0             # 0.0 – 1.0


@dataclass
class ExecutionResult:
    task_id: str
    agent_type: str = ""
    output: str = ""
    success: bool = True
    latency_ms: float = 0.0
    review: Optional[ReviewResult] = None


# ── Workflow State ────────────────────────────────────────────────

@dataclass
class WorkflowState:
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    idea: str = ""
    phase: WorkflowPhase = WorkflowPhase.CREATED
    brainstorm: Optional[BrainstormResult] = None
    tasks: List[PlanTask] = field(default_factory=list)
    executions: List[ExecutionResult] = field(default_factory=list)
    final_review: Optional[ReviewResult] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: Optional[str] = None

    _PHASE_ORDER = {
        WorkflowPhase.CREATED:    {WorkflowPhase.BRAINSTORM, WorkflowPhase.FAILED},
        WorkflowPhase.BRAINSTORM: {WorkflowPhase.PLAN, WorkflowPhase.FAILED},
        WorkflowPhase.PLAN:       {WorkflowPhase.EXECUTE, WorkflowPhase.FAILED},
        WorkflowPhase.EXECUTE:    {WorkflowPhase.REVIEW, WorkflowPhase.FAILED},
        WorkflowPhase.REVIEW:     {WorkflowPhase.COMPLETE, WorkflowPhase.EXECUTE, WorkflowPhase.FAILED},
        WorkflowPhase.COMPLETE:   set(),
        WorkflowPhase.FAILED:     {WorkflowPhase.CREATED},  # allow retry
    }

    def advance(self, phase: WorkflowPhase) -> None:
        allowed = self._PHASE_ORDER.get(self.phase, set())
        if phase not in allowed:
            raise ValueError(
                f"Cannot transition from '{self.phase.value}' to '{phase.value}'. "
                f"Allowed: {[p.value for p in allowed]}"
            )
        self.phase = phase
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "idea": self.idea[:200],
            "phase": self.phase.value,
            "tasks_total": len(self.tasks),
            "tasks_done": sum(1 for t in self.tasks if t.status == "done"),
            "executions": len(self.executions),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }
