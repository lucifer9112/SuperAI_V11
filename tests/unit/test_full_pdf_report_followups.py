from __future__ import annotations

import asyncio
import io
import time
from pathlib import Path

import aiosqlite
import pytest
from starlette.datastructures import UploadFile

from backend.api.v1.files import MAX_UPLOAD_BYTES, upload
from backend.core.exceptions import BadRequestError
from backend.intelligence.self_improvement import FailureDetector
from backend.knowledge.rag_engine import RAGEngine
from backend.memory.advanced_memory import EpisodicMemory
from backend.models.schemas import FileProcessResponse
from backend.multimodal.fusion_engine import MultimodalFusionEngine, MultimodalInput
from backend.personality.personality_engine import PersonalityEngine
from backend.rlhf.rlhf_pipeline import FeedbackToRLHFConverter
from backend.security_ai.ai_security import BehavioralMonitor
from backend.services.monitoring_service import MonitoringService
from backend.services.simple_memory_service import SimpleMemoryService


def _memory_cfg(db_path: Path):
    return type("Cfg", (), {"db_path": str(db_path), "context_window": 5})()


def _personality_cfg():
    return type(
        "Cfg",
        (),
        {
            "enabled": True,
            "traits": {},
            "name": "SuperAI",
            "session_ttl_s": 60,
            "max_sessions": 1,
        },
    )()


def _rag_cfg():
    return type(
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


def _fusion_cfg():
    return type(
        "Cfg",
        (),
        {
            "enabled": True,
            "fusion_strategy": "sequential",
            "text_weight": 0.2,
            "image_weight": 0.5,
            "audio_weight": 0.3,
        },
    )()


def test_failure_detector_ignores_plain_actually():
    detector = FailureDetector()

    assert detector.detect_correction("Actually, I wanted a shorter answer.", "sess") is None

    record = detector.detect_correction("Actually, that's wrong.", "sess")
    assert record is not None
    assert record.failure_type == "correction"


@pytest.mark.asyncio
async def test_simple_memory_enables_sqlite_wal(tmp_path: Path):
    svc = SimpleMemoryService(_memory_cfg(tmp_path / "simple.db"))
    await svc.init()
    try:
        db = svc._require_db()
        async with db.execute("PRAGMA journal_mode") as cursor:
            journal_mode = (await cursor.fetchone())[0]
        async with db.execute("PRAGMA busy_timeout") as cursor:
            busy_timeout = (await cursor.fetchone())[0]

        assert str(journal_mode).lower() == "wal"
        assert int(busy_timeout) == 5000
    finally:
        await svc.close()


@pytest.mark.asyncio
async def test_episodic_memory_requires_init(tmp_path: Path):
    episodic = EpisodicMemory(str(tmp_path / "episodic.db"))

    with pytest.raises(RuntimeError, match="not initialized"):
        await episodic.recall("sess")


def test_personality_engine_prunes_stale_sessions():
    engine = PersonalityEngine(_personality_cfg())

    engine.update_session("old", "hello there", "neutral")
    engine._emotions["old"].last_updated = time.time() - 500
    engine._adapter._profiles["old"].last_updated = time.time() - 500

    engine.update_session("new", "need help with code", "curious")

    assert "old" not in engine._emotions
    assert "old" not in engine._adapter._profiles
    assert engine.session_emotion("new") == "curious"


def test_behavioral_monitor_prunes_stale_profiles():
    monitor = BehavioralMonitor(session_ttl_s=60, max_sessions=1)

    monitor.record("old", is_threat=False)
    monitor._profiles["old"].last_seen = time.time() - 500

    monitor.record("new", is_threat=True)

    assert "old" not in monitor._profiles
    assert "new" in monitor._profiles


class _FakeRetriever:
    def __init__(self) -> None:
        self.calls = 0

    async def retrieve(self, query: str):
        self.calls += 1
        await asyncio.sleep(0.05)
        return [{"title": query, "body": "Body text for testing", "url": "https://example.com"}]


class _FakeIndex:
    def search(self, query, chunks, top_k):  # pragma: no cover - trivial helper
        del query
        return chunks[:top_k]


@pytest.mark.asyncio
async def test_rag_engine_dedupes_inflight_requests():
    engine = RAGEngine(_rag_cfg())
    retriever = _FakeRetriever()
    engine._retriever = retriever
    engine._index = _FakeIndex()

    ctx1, ctx2 = await asyncio.gather(
        engine.retrieve_context("same query"),
        engine.retrieve_context("same query"),
    )

    assert retriever.calls == 1
    assert ctx1 == ctx2
    assert "[Retrieved Knowledge]" in ctx1


class _DummyOrchestrator:
    async def process_file(self, filename: str, data: bytes, question: str, session_id: str | None):
        del data, question, session_id
        return FileProcessResponse(filename=filename, file_type="txt", summary="ok", content="")


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file():
    big_upload = UploadFile(filename="big.txt", file=io.BytesIO(b"x" * (MAX_UPLOAD_BYTES + 1)))

    with pytest.raises(BadRequestError, match="too large"):
        await upload(
            file=big_upload,
            question="Summarise this document.",
            session_id="sess",
            orch=_DummyOrchestrator(),
        )


@pytest.mark.asyncio
async def test_rlhf_converter_skips_synthetic_truncation_pairs(tmp_path: Path):
    feedback_db = tmp_path / "feedback.db"
    conv_db = tmp_path / "conv.db"

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
            ("sess", "question", " ".join(["long-answer"] * 30), "resp-1", time.time()),
        )
        await db.commit()

    converter = FeedbackToRLHFConverter(str(feedback_db), str(conv_db))
    pairs = await converter.build_pairs(min_pairs=2)

    assert pairs == []


@pytest.mark.asyncio
async def test_multimodal_fusion_normalizes_active_weights():
    class _Vision:
        async def analyze(self, image_b64: str, question: str):
            del image_b64, question
            return type("Result", (), {"description": "a cat"})()

    class _Voice:
        async def transcribe(self, audio_bytes: bytes):
            del audio_bytes
            return type("Result", (), {"transcript": "hello"})()

    engine = MultimodalFusionEngine(_fusion_cfg(), _Vision(), _Voice())
    result = await engine.fuse(MultimodalInput(text="describe this", image_b64="abc", audio_bytes=b"123"))

    assert round(result.text_weight + result.image_weight + result.audio_weight, 6) == 1.0
    assert "[Image weight=" in result.unified_prompt
    assert "[Audio weight=" in result.unified_prompt


def test_monitoring_summary_tracks_extended_counters():
    mon = MonitoringService()
    mon.record_error("inference")
    mon.record_tool("web_search", success=False)
    mon.record_security_event("flagged_session", blocked=True)
    mon.record_cache_event("rag", "hit")

    summary = mon.summary()

    assert summary["errors_by_kind"]["inference"] == 1
    assert summary["tool_calls"]["web_search"] == 1
    assert summary["tool_failures"]["web_search"] == 1
    assert summary["security_events"]["flagged_session|blocked=true"] == 1
    assert summary["cache_events"]["rag:hit"] == 1
