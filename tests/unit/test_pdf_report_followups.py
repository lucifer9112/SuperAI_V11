from __future__ import annotations

import os
import time
from pathlib import Path

import aiosqlite
import pytest

from backend.app.factory import create_app
from backend.app.dependencies import ServiceContainer
from backend.config.settings import AppSettings
from backend.controllers.master_controller import MasterController
from backend.models.schemas import ChatRequest
from backend.services.simple_memory_service import SimpleMemoryService


class _StreamModelLoader:
    async def infer(self, model_name: str, prompt: str, max_tokens: int, temperature: float):
        del prompt, max_tokens, temperature
        return f"infer-{model_name}", 2

    async def stream(self, model_name: str, prompt: str, max_tokens: int, temperature: float):
        del model_name, prompt, max_tokens, temperature
        for token in ["hello", " ", "world"]:
            yield token

    async def count_tokens(self, model_name: str, text: str) -> int:
        del model_name
        return len(text.split())

    def loaded_models(self):
        return ["stream-model"]


class _Security:
    enabled = True
    output_filter = True

    def validate(self, prompt: str):
        del prompt
        return False

    def filter_output(self, text: str):
        return text


class _Monitoring:
    def __init__(self) -> None:
        self.calls = 0

    def record_request(self, **kwargs) -> None:
        del kwargs
        self.calls += 1


def test_factory_mounts_websocket_route():
    app = create_app()
    assert any(route.path == "/ws/chat" for route in app.routes)


@pytest.mark.asyncio
async def test_master_controller_streams_multiple_tokens_and_persists_turn(tmp_path: Path):
    memory = SimpleMemoryService(type("Cfg", (), {"db_path": str(tmp_path / "chat.db"), "context_window": 5})())
    await memory.init()
    try:
        monitoring = _Monitoring()
        controller = MasterController(
            model_loader=_StreamModelLoader(),
            memory_svc=memory,
            security_engine=_Security(),
            monitoring_svc=monitoring,
        )

        tokens = []
        async for token in controller.stream(ChatRequest(prompt="stream please", session_id="sess-stream")):
            tokens.append(token)

        history = await memory.get_history("sess-stream", limit=5)
        assert tokens == ["hello", " ", "world"]
        assert history[0]["assistant"] == "hello world"
        assert monitoring.calls == 1
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_container_load_tools_builds_registry():
    container = ServiceContainer()
    container._model_loader = None
    await container._load_tools()

    assert container._tool_engine is not None
    assert container._tool_engine._reg is not None
    assert container._tool_engine._reg.get("web_search") is not None


@pytest.mark.asyncio
async def test_rlhf_converter_supports_simple_conversation_turns(tmp_path: Path):
    from backend.rlhf.rlhf_pipeline import FeedbackToRLHFConverter

    feedback_db = tmp_path / "feedback.db"
    conv_db = tmp_path / "conv.db"

    async with aiosqlite.connect(feedback_db) as db:
        await db.execute("CREATE TABLE feedback (response_id TEXT, score INTEGER)")
        await db.executemany(
            "INSERT INTO feedback VALUES (?, ?)",
            [("resp-good", 5), ("resp-bad", 1)],
        )
        await db.commit()

    async with aiosqlite.connect(conv_db) as db:
        await db.execute(
            "CREATE TABLE simple_conversation_turns (response_id TEXT, user_text TEXT, assistant_text TEXT, created_at REAL)"
        )
        await db.executemany(
            "INSERT INTO simple_conversation_turns VALUES (?, ?, ?, ?)",
            [
                ("resp-good", "good prompt", "good response with enough words to create a preference pair for training", time.time()),
                ("resp-bad", "bad prompt", "bad response with enough words to also be valid for pairing", time.time()),
            ],
        )
        await db.commit()

    converter = FeedbackToRLHFConverter(str(feedback_db), str(conv_db))
    pairs = await converter.build_pairs(min_pairs=1)

    assert len(pairs) == 1
    assert pairs[0]["prompt"] == "good prompt"


@pytest.mark.asyncio
async def test_learning_builder_supports_simple_conversation_turns(tmp_path: Path):
    from backend.intelligence.learning_pipeline import DatasetBuilder

    class Cfg:
        dataset_path = str(tmp_path / "training")
        min_quality_score = 4

    feedback_db = tmp_path / "feedback.db"
    conv_db = tmp_path / "conv.db"

    async with aiosqlite.connect(feedback_db) as db:
        await db.execute("CREATE TABLE feedback (response_id TEXT, score INTEGER, comment TEXT)")
        await db.execute("INSERT INTO feedback VALUES (?, ?, ?)", ("resp-1", 5, "great"))
        await db.commit()

    async with aiosqlite.connect(conv_db) as db:
        await db.execute(
            "CREATE TABLE simple_conversation_turns (response_id TEXT, user_text TEXT, assistant_text TEXT)"
        )
        await db.execute(
            "INSERT INTO simple_conversation_turns VALUES (?, ?, ?)",
            ("resp-1", "matched prompt", "matched answer"),
        )
        await db.commit()

    builder = DatasetBuilder(Cfg())
    count = await builder.build_from_feedback(str(feedback_db), str(conv_db))

    assert count == 1


def test_app_settings_read_feature_flags_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPERAI_MODE", "advanced")
    monkeypatch.setenv("FEATURES__ENABLE_TOOLS", "true")
    monkeypatch.setenv("FEATURES__ENABLE_RLHF", "true")

    settings = AppSettings()

    assert settings.is_minimal is False
    assert settings.active_features["enable_tools"] is True
    assert settings.active_features["enable_rlhf"] is True


def test_app_settings_reject_default_secret_in_production():
    with pytest.raises(ValueError):
        AppSettings(server={"environment": "production"}, security={"secret_key": "change-me-in-production"})
