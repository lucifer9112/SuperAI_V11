"""
SuperAI V12 — tests/unit/test_v12_workflow.py
Unit tests for Step 4: Agentic Workflow Engine
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── Models ────────────────────────────────────────────────────────

class TestWorkflowModels:

    def test_workflow_state_defaults(self):
        from backend.workflow.models import WorkflowState, WorkflowPhase
        wf = WorkflowState(idea="Build a REST API")
        assert wf.idea == "Build a REST API"
        assert wf.phase == WorkflowPhase.CREATED
        assert wf.workflow_id
        assert wf.tasks == []
        assert wf.executions == []

    def test_workflow_state_advance(self):
        from backend.workflow.models import WorkflowState, WorkflowPhase
        wf = WorkflowState(idea="test")
        wf.advance(WorkflowPhase.BRAINSTORM)
        assert wf.phase == WorkflowPhase.BRAINSTORM
        wf.advance(WorkflowPhase.PLAN)
        assert wf.phase == WorkflowPhase.PLAN

    def test_workflow_state_to_dict(self):
        from backend.workflow.models import WorkflowState
        wf = WorkflowState(idea="Build something")
        d = wf.to_dict()
        assert "workflow_id" in d
        assert "idea" in d
        assert "phase" in d
        assert d["tasks_total"] == 0
        assert d["tasks_done"] == 0

    def test_plan_task_defaults(self):
        from backend.workflow.models import PlanTask
        t = PlanTask(description="Create models.py")
        assert t.task_id
        assert t.status == "pending"
        assert t.result is None

    def test_review_result_structure(self):
        from backend.workflow.models import ReviewResult, ReviewIssue, IssueSeverity
        review = ReviewResult(
            passed=False,
            issues=[ReviewIssue(severity=IssueSeverity.CRITICAL, description="Bug found")],
            summary="Issues found",
            score=0.3,
        )
        assert not review.passed
        assert len(review.issues) == 1
        assert review.issues[0].severity == IssueSeverity.CRITICAL

    def test_brainstorm_result(self):
        from backend.workflow.models import BrainstormResult
        result = BrainstormResult(idea="AI chatbot", questions=["Who?", "What?"])
        assert result.idea == "AI chatbot"
        assert len(result.questions) == 2


# ── Brainstorm Engine ─────────────────────────────────────────────

class TestBrainstormEngine:

    def setup_method(self):
        from backend.workflow.brainstorm import BrainstormEngine
        self.engine = BrainstormEngine(model_loader=None)

    @pytest.mark.asyncio
    async def test_fallback_questions(self):
        questions = await self.engine.generate_questions("Build a REST API")
        assert len(questions) >= 3
        assert all(isinstance(q, str) for q in questions)

    @pytest.mark.asyncio
    async def test_fallback_design(self):
        result = await self.engine.refine_design("Build an API", {"Q1": "A1"})
        assert result.idea == "Build an API"
        assert result.refined_design

    def test_parse_questions(self):
        text = "Q: What scope?\nQ: Who uses it?\nQ: Key features?"
        from backend.workflow.brainstorm import BrainstormEngine
        questions = BrainstormEngine._parse_questions(text)
        assert len(questions) == 3

    def test_parse_sections(self):
        text = "## Overview\nA project.\n## Features\n- Feature one\n"
        from backend.workflow.brainstorm import BrainstormEngine
        sections = BrainstormEngine._parse_sections(text)
        assert len(sections) == 2
        assert sections[0]["title"] == "Overview"


# ── Planner ───────────────────────────────────────────────────────

class TestWorkflowPlanner:

    def setup_method(self):
        from backend.workflow.planner import WorkflowPlanner
        self.planner = WorkflowPlanner(model_loader=None)

    @pytest.mark.asyncio
    async def test_fallback_plan(self):
        tasks = await self.planner.create_plan("Build an API server")
        assert len(tasks) >= 3
        assert all(t.description for t in tasks)

    def test_parse_tasks(self):
        text = (
            "1. TASK: Set up project\n"
            "FILES: main.py, models.py\n"
            "VERIFY: Files exist\n"
            "DEPENDS: none\n\n"
            "2. TASK: Add endpoints\n"
            "FILES: routes.py\n"
            "VERIFY: Tests pass\n"
            "DEPENDS: 1\n"
        )
        from backend.workflow.planner import WorkflowPlanner
        tasks = WorkflowPlanner._parse_tasks(text)
        assert len(tasks) == 2
        assert tasks[0].description == "Set up project"
        assert "main.py" in tasks[0].target_files


# ── Reviewer ──────────────────────────────────────────────────────

class TestWorkflowReviewer:

    def setup_method(self):
        from backend.workflow.reviewer import WorkflowReviewer
        self.reviewer = WorkflowReviewer(model_loader=None)

    @pytest.mark.asyncio
    async def test_heuristic_review_good_output(self):
        result = await self.reviewer.review(
            output="This is a complete implementation with proper error handling.",
            task_description="Implement feature",
        )
        assert result.passed
        assert result.score > 0.5

    @pytest.mark.asyncio
    async def test_heuristic_review_empty_output(self):
        result = await self.reviewer.review(output="", task_description="Do thing")
        assert not result.passed
        assert len(result.issues) > 0

    @pytest.mark.asyncio
    async def test_heuristic_review_error_output(self):
        result = await self.reviewer.review(
            output="Traceback (most recent call last):\n  Error occurred",
            task_description="Fix bug",
        )
        assert len(result.issues) >= 1

    def test_parse_review_output(self):
        text = (
            "SEVERITY: warning\n"
            "ISSUE: Missing error handling\n"
            "LOCATION: line 10\n"
            "FIX: Add try/except\n"
            "OVERALL: pass\n"
            "SCORE: 0.7\n"
            "SUMMARY: Mostly good\n"
        )
        from backend.workflow.reviewer import WorkflowReviewer
        result = WorkflowReviewer._parse_review(text)
        assert result.passed
        assert len(result.issues) == 1
        assert result.score == 0.7


# ── Workflow Engine ───────────────────────────────────────────────

class TestWorkflowEngine:

    def setup_method(self):
        from backend.workflow.engine import WorkflowEngine
        self.engine = WorkflowEngine(model_loader=None)

    def test_create_workflow(self):
        wf = self.engine.create("Build a chatbot")
        assert wf.idea == "Build a chatbot"
        assert wf.workflow_id

    def test_get_workflow(self):
        wf = self.engine.create("Test idea")
        found = self.engine.get(wf.workflow_id)
        assert found is not None
        assert found.idea == "Test idea"

    def test_list_workflows(self):
        self.engine.create("Idea A")
        self.engine.create("Idea B")
        all_wf = self.engine.list_all()
        assert len(all_wf) >= 2

    def test_max_workflows_limit(self):
        engine = self.__class__.__new__(self.__class__)
        from backend.workflow.engine import WorkflowEngine
        eng = WorkflowEngine(model_loader=None, max_workflows=2)
        eng.create("A")
        eng.create("B")
        with pytest.raises(ValueError, match="Max active"):
            eng.create("C")

    @pytest.mark.asyncio
    async def test_brainstorm_phase(self):
        wf = self.engine.create("Build a REST API")
        wf = await self.engine.brainstorm(wf.workflow_id)
        from backend.workflow.models import WorkflowPhase
        assert wf.phase == WorkflowPhase.BRAINSTORM
        assert wf.brainstorm is not None

    @pytest.mark.asyncio
    async def test_plan_phase(self):
        wf = self.engine.create("Build API")
        await self.engine.brainstorm(wf.workflow_id)
        wf = await self.engine.plan(wf.workflow_id)
        from backend.workflow.models import WorkflowPhase
        assert wf.phase == WorkflowPhase.PLAN
        assert len(wf.tasks) > 0

    @pytest.mark.asyncio
    async def test_execute_phase(self):
        wf = self.engine.create("Build something")
        await self.engine.brainstorm(wf.workflow_id)
        await self.engine.plan(wf.workflow_id)
        wf = await self.engine.execute(wf.workflow_id)
        from backend.workflow.models import WorkflowPhase
        assert wf.phase in (WorkflowPhase.EXECUTE, WorkflowPhase.REVIEW)

    @pytest.mark.asyncio
    async def test_nonexistent_workflow_raises(self):
        with pytest.raises(ValueError, match="not found"):
            await self.engine.brainstorm("fake-id")
