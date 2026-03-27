from __future__ import annotations

from pathlib import Path

import pytest

from backend.config.settings import AppSettings, FeatureGates, LoggingSettings, MemorySettings, ModelSettings, PersonalitySettings, SecuritySettings, ServerSettings
from backend.controllers.master_controller import MasterController
from backend.models.schemas import ChatRequest, MemorySearchRequest, MemoryStoreRequest
from backend.services.simple_memory_service import SimpleMemoryService


class FakeModelLoader:
    async def infer(self, model_name: str, prompt: str, max_tokens: int, temperature: float):
        del prompt, max_tokens, temperature
        return f"reply-from-{model_name}", 7

    def loaded_models(self):
        return ["fake-model"]


class FakeSecurity:
    def validate(self, prompt: str) -> bool:
        del prompt
        return False

    def filter_output(self, text: str) -> str:
        return text


class FakeMonitoring:
    def __init__(self) -> None:
        self.calls = 0

    def record_request(self, **kwargs) -> None:
        del kwargs
        self.calls += 1


@pytest.mark.asyncio
async def test_simple_memory_service_round_trip(tmp_path: Path):
    memory = SimpleMemoryService(
        MemorySettings(
            enabled=True,
            db_path=str(tmp_path / "memory.db"),
            context_window=3,
            max_history_turns=10,
        )
    )
    await memory.init()
    try:
        entry_id = await memory.store(
            MemoryStoreRequest(content="superai smoke memory", session_id="s1", tags=["demo"], priority=1.5)
        )
        await memory.save_turn("s1", "hello", "world", response_id="r1")

        search = await memory.search(MemorySearchRequest(query="smoke", session_id="s1", top_k=5))
        history = await memory.get_history("s1", limit=5)
        context = await memory.get_context("s1", prompt="hello")

        assert entry_id
        assert search.total_found == 1
        assert history[0]["response_id"] == "r1"
        assert context[0]["assistant"] == "world"
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_master_controller_processes_minimal_request(tmp_path: Path):
    memory = SimpleMemoryService(MemorySettings(enabled=True, db_path=str(tmp_path / "chat.db")))
    await memory.init()
    try:
        monitoring = FakeMonitoring()
        controller = MasterController(
            model_loader=FakeModelLoader(),
            memory_svc=memory,
            security_engine=FakeSecurity(),
            monitoring_svc=monitoring,
        )

        result = await controller.process(ChatRequest(prompt="Say hello", session_id="sess-1"))
        history = await memory.get_history("sess-1", limit=5)

        assert result.answer == "reply-from-Qwen/Qwen2.5-0.5B-Instruct"
        assert result.session_id == "sess-1"
        assert history[0]["assistant"] == result.answer
        assert monitoring.calls == 1
    finally:
        await memory.close()


def test_app_settings_active_features_follow_mode():
    settings = AppSettings(
        mode="advanced",
        server=ServerSettings(),
        models=ModelSettings(),
        memory=MemorySettings(),
        security=SecuritySettings(),
        personality=PersonalitySettings(),
        logging=LoggingSettings(),
        features=FeatureGates(enable_workflow=True, enable_skills=True),
    )

    assert settings.is_minimal is False
    assert settings.active_features == {
        "enable_workflow": True,
        "enable_skills": True,
    }
