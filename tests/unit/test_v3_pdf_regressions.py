from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest
from fastapi import HTTPException

from backend.agents.specialized import (
    CodingAgentProfile,
    PlanningAgentProfile,
    ReasoningAgentProfile,
    ResearchAgentProfile,
)
from backend.api.v1 import router as api_router_module
from backend.api.v1.intelligence import suggestions
from backend.api.v1.rlhf_api import GRPORequest, grpo_train
from backend.core.exceptions import SecurityViolationError
from backend.core.orchestrator import OrchestratorV11
from backend.models.schemas import ChatRequest, TaskType
from backend.rlhf.rlhf_pipeline import FeedbackToRLHFConverter
from backend.tools.tool_executor import _validate_python_code


class _BlockedAssessment:
    blocked = True
    threat_type = "injection"
    confidence = 0.99


class _BlockingAISecurity:
    async def assess(self, prompt: str, session_id: str):
        del prompt, session_id
        return _BlockedAssessment()


class _UnusedModelLoader:
    async def infer(self, *args, **kwargs):  # pragma: no cover - should never run
        raise AssertionError("Fast path should not reach inference when AI security blocks")


class _TaskRouter:
    def route(self, prompt: str):
        del prompt
        return TaskType.CHAT

    def select_model(self, task_type):
        del task_type
        return "demo-model"


class _Monitoring:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def record_error(self, kind: str) -> None:
        self.errors.append(kind)


@pytest.mark.asyncio
async def test_fast_path_still_runs_ai_security_before_dispatch():
    orch = OrchestratorV11(
        model_loader=_UnusedModelLoader(),
        memory_svc=None,
        agent_svc=None,
        voice_svc=None,
        vision_svc=None,
        security_engine=None,
        task_router=_TaskRouter(),
        monitoring_svc=SimpleNamespace(record_request=lambda **kwargs: None),
        personality_cfg=SimpleNamespace(system_prompt="You are SuperAI"),
        ai_security=_BlockingAISecurity(),
    )

    with pytest.raises(SecurityViolationError, match="AI security blocked"):
        await orch.chat(ChatRequest(prompt="hello", session_id="sess"))


@pytest.mark.asyncio
async def test_grpo_train_returns_api_error_on_failed_run():
    class _FakeRLHF:
        async def run_grpo(self, model_name: str, prompts: list[str], epochs: int):
            del model_name, prompts, epochs
            return SimpleNamespace(status="failed", metrics={"message": "GRPO worker crashed"}, run_id="grpo-1")

    response = await grpo_train(GRPORequest(prompts=["hello"]), rlhf=_FakeRLHF())

    assert response.success is False
    assert response.error == "GRPO worker crashed"


def test_ast_validator_blocks_builtins_subscript_access():
    blocked = _validate_python_code("__builtins__['open']('secret.txt')")
    assert blocked == "Blocked subscript: __builtins__"


@pytest.mark.asyncio
async def test_rest_auth_can_be_enabled_outside_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_router_module.settings.server, "environment", "development")
    monkeypatch.setattr(api_router_module.settings.security, "require_auth", True)
    monkeypatch.setattr(api_router_module.settings.security, "secret_key", "top-secret")

    with pytest.raises(HTTPException) as exc_info:
        await api_router_module.require_api_key_if_needed(None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_suggestions_alias_surfaces_self_improvement_output():
    class _Engine:
        async def suggest_improvements(self):
            return ["Enable grounded retrieval for correction-heavy sessions."]

    response = await suggestions(svc=_Engine())

    assert response.success is True
    assert response.data["count"] == 1
    assert response.data["suggestions"][0].startswith("Enable grounded retrieval")


@pytest.mark.asyncio
async def test_rlhf_converter_records_monitoring_on_insufficient_pairs(tmp_path: Path):
    feedback_db = tmp_path / "feedback.db"
    conv_db = tmp_path / "conv.db"
    monitoring = _Monitoring()

    async with aiosqlite.connect(feedback_db) as db:
        await db.execute("CREATE TABLE feedback (response_id TEXT, score INTEGER)")
        await db.execute("INSERT INTO feedback VALUES (?, ?)", ("resp-1", 5))
        await db.commit()

    async with aiosqlite.connect(conv_db) as db:
        await db.execute(
            """
            CREATE TABLE simple_conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                user_text TEXT,
                assistant_text TEXT,
                response_id TEXT,
                created_at REAL
            )
            """
        )
        await db.execute(
            """
            INSERT INTO simple_conversation_turns
            (session_id, user_text, assistant_text, response_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("sess", "question", "short", "resp-1", time.time()),
        )
        await db.commit()

    converter = FeedbackToRLHFConverter(str(feedback_db), str(conv_db), monitoring=monitoring)
    pairs = await converter.build_pairs(min_pairs=2)

    assert pairs == []
    assert monitoring.errors == ["rlhf_insufficient_pairs"]


def test_specialized_agent_profiles_exist():
    assert ResearchAgentProfile.SYSTEM_PROMPT
    assert CodingAgentProfile.SYSTEM_PROMPT
    assert ReasoningAgentProfile.SYSTEM_PROMPT
    assert PlanningAgentProfile.SYSTEM_PROMPT
