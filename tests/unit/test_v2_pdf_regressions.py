from __future__ import annotations

import asyncio
import importlib
import os
import subprocess
from types import SimpleNamespace

import pytest

from backend.api.v1.code import code_action
from backend.api.v1.files import file_qa
from backend.api.v1.personality_api import ParallelAgentRequest, parallel_agents
from backend.api.v1.rlhf_api import DPORequest, dpo_train
from backend.config.settings import AppSettings, SecuritySettings
from backend.core.orchestrator import OrchestratorV11
from backend.knowledge.rag_engine import RAGEngine
from backend.memory import memory_v9
from backend.models.schemas import ChatRequest, CodeRequest, TaskType
from backend.multimodal.fusion_engine import MultimodalFusionEngine, MultimodalInput
from backend.tools import tool_executor


@pytest.mark.asyncio
async def test_orchestrator_dependent_routes_fail_gracefully_without_orchestrator():
    code_result = await code_action(CodeRequest(description="demo"), orch=None)
    file_result = await file_qa("file-1", question="What is this?", orch=None)
    agent_result = await parallel_agents(ParallelAgentRequest(goal="help"), orch=None)

    assert code_result.success is False
    assert file_result.success is False
    assert agent_result.success is False
    assert code_result.error == "Orchestrator not loaded"


def test_secret_key_validation_runs_once_at_app_level(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SERVER__ENVIRONMENT", "production")

    # SecuritySettings alone should not raise now; AppSettings remains the single gatekeeper.
    security = SecuritySettings()
    assert security.secret_key == "change-me-in-production"

    with pytest.raises(ValueError, match="SECRET_KEY must be changed in production"):
        AppSettings(server={"environment": "production"}, security={"secret_key": "change-me-in-production"})


class _SlowRetriever:
    async def retrieve(self, query: str):
        await asyncio.sleep(5)
        return [{"title": query, "body": "body", "url": "https://example.com"}]


class _Index:
    def search(self, query, chunks, top_k):
        del query
        return chunks[:top_k]


@pytest.mark.asyncio
async def test_rag_engine_releases_followers_when_leader_is_cancelled():
    cfg = type(
        "Cfg",
        (),
        {
            "enabled": True,
            "chunk_size": 20,
            "chunk_overlap": 5,
            "top_k_chunks": 1,
            "max_web_results": 3,
            "cache_ttl_s": 3600,
        },
    )()
    engine = RAGEngine(cfg)
    engine._retriever = _SlowRetriever()
    engine._index = _Index()

    leader = asyncio.create_task(engine.retrieve_context("cancel-me"))
    await asyncio.sleep(0.05)
    follower = asyncio.create_task(engine.retrieve_context("cancel-me"))
    await asyncio.sleep(0.05)
    leader.cancel()

    with pytest.raises(asyncio.CancelledError):
        await leader

    result = await asyncio.wait_for(follower, timeout=1)
    assert result == ""
    assert engine._inflight == {}


def test_code_execute_blocks_dunder_builtin_access():
    blocked = tool_executor._validate_python_code("__builtins__['print']('hi')")
    assert blocked == "Blocked name: __builtins__"


@pytest.mark.asyncio
async def test_code_execute_preserves_process_environment(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class _Result:
        stdout = "ok"
        stderr = ""

    def fake_run(*args, **kwargs):
        del args
        captured["env"] = kwargs["env"]
        return _Result()

    monkeypatch.setitem(os.environ, "PATH", "C:\\Windows\\System32")
    monkeypatch.setattr(tool_executor.subprocess, "run", fake_run)

    output = await tool_executor._code_execute("print('ok')")

    assert output == "ok"
    assert captured["env"]["PATH"] == "C:\\Windows\\System32"


def test_memory_v9_access_raises_import_error():
    with pytest.raises(ImportError, match="memory_v9 is no longer available"):
        _ = memory_v9.MemoryServiceV9


class _FakeModelLoader:
    def __init__(self) -> None:
        self.calls = 0

    async def infer(self, model_name: str, prompt: str, max_tokens: int, temperature: float):
        del prompt, max_tokens, temperature
        self.calls += 1
        return f"answer-from-{model_name}", 4

    async def stream(self, model_name: str, prompt: str, max_tokens: int, temperature: float):
        del model_name, prompt, max_tokens, temperature
        for token in ["fast", " ", "path"]:
            yield token

    async def count_tokens(self, model_name: str, text: str) -> int:
        del model_name
        return len(text.split())


class _FakeMemory:
    def __init__(self) -> None:
        self.context_calls = 0
        self.saved = []

    async def get_context(self, session_id: str, prompt: str):
        del session_id, prompt
        self.context_calls += 1
        return [{"user": "u", "assistant": "a"}]

    async def save_turn(self, session_id: str, user_text: str, assistant_text: str, response_id: str = ""):
        self.saved.append((session_id, user_text, assistant_text, response_id))


class _FakeSecurity:
    cfg = SimpleNamespace(enabled=False, output_filter=False)

    def validate(self, prompt: str):
        del prompt
        return False

    def filter_output(self, text: str):
        return text


class _FakeMonitor:
    def __init__(self) -> None:
        self.requests = 0

    def record_request(self, **kwargs):
        del kwargs
        self.requests += 1


class _HeavyComponent:
    def __init__(self) -> None:
        self.calls = 0

    async def check_correction(self, prompt: str, session_id: str):
        del prompt, session_id
        self.calls += 1

    async def retrieve_context(self, prompt: str):
        del prompt
        self.calls += 1
        return "rag"

    async def process(self, prompt: str, autonomy_level: int = 2):
        del prompt, autonomy_level
        self.calls += 1
        return SimpleNamespace(tools_used=[], enriched_prompt="")

    async def reflect(self, prompt: str, answer: str, task_type: str, model_name: str):
        del prompt, answer, task_type, model_name
        self.calls += 1
        return SimpleNamespace(final_answer="reflected", confidence=0.9, reflection_notes="")

    async def score_response(self, prompt: str, answer: str):
        del prompt, answer
        self.calls += 1
        return 0.0


class _TaskRouter:
    def route(self, prompt: str):
        del prompt
        return TaskType.CHAT

    def select_model(self, task_type):
        del task_type
        return "demo-model"


@pytest.mark.asyncio
async def test_orchestrator_fast_path_skips_heavy_pipeline_for_simple_chat():
    model_loader = _FakeModelLoader()
    memory = _FakeMemory()
    monitor = _FakeMonitor()
    improve = _HeavyComponent()
    rag = _HeavyComponent()
    tools = _HeavyComponent()
    reflection = _HeavyComponent()
    rlhf = _HeavyComponent()

    orch = OrchestratorV11(
        model_loader=model_loader,
        memory_svc=memory,
        agent_svc=None,
        voice_svc=None,
        vision_svc=None,
        security_engine=_FakeSecurity(),
        task_router=_TaskRouter(),
        monitoring_svc=monitor,
        personality_cfg=SimpleNamespace(system_prompt="You are SuperAI"),
        reflection_engine=reflection,
        rag_engine=rag,
        self_improvement=improve,
        rlhf_pipeline=rlhf,
        tool_engine=tools,
    )

    result = await orch.chat(ChatRequest(prompt="hello", session_id="sess-fast", max_tokens=32))

    assert result.answer == "answer-from-demo-model"
    assert memory.context_calls == 0
    assert len(memory.saved) == 1
    assert improve.calls == 0
    assert rag.calls == 0
    assert tools.calls == 0
    assert reflection.calls == 0
    assert rlhf.calls == 0
    assert monitor.requests == 1


def test_advanced_api_module_imports_after_dependency_fix():
    module = importlib.import_module("backend.api.v1.intelligence")
    assert hasattr(module, "router")


@pytest.mark.asyncio
async def test_dpo_train_returns_api_error_on_failed_run():
    class _FakeDPO:
        _is_running = False

    class _FakeRLHF:
        _dpo = _FakeDPO()

        async def run_dpo(self, model_name: str, epochs: int):
            del model_name, epochs
            return SimpleNamespace(status="failed", metrics={"message": "Need >=4 pairs, got 1"}, run_id="none")

    response = await dpo_train(DPORequest(), rlhf=_FakeRLHF())

    assert response.success is False
    assert response.error == "Need >=4 pairs, got 1"


@pytest.mark.asyncio
async def test_multimodal_fusion_includes_priority_order():
    class _Vision:
        async def analyze(self, image_b64: str, question: str):
            del image_b64, question
            return type("Result", (), {"description": "diagram"})()

    class _Voice:
        async def transcribe(self, audio_bytes: bytes):
            del audio_bytes
            return type("Result", (), {"transcript": "spoken context"})()

    cfg = type(
        "Cfg",
        (),
        {"enabled": True, "fusion_strategy": "sequential", "text_weight": 0.2, "image_weight": 0.5, "audio_weight": 0.3},
    )()
    engine = MultimodalFusionEngine(cfg, _Vision(), _Voice())

    result = await engine.fuse(MultimodalInput(text="base text", image_b64="abc", audio_bytes=b"123"))

    assert "Priority order: Image(0.50) > Audio(0.30) > Text(0.20)" in result.unified_prompt
    assert "[Image weight=0.50]" in result.unified_prompt
