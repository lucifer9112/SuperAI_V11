import json
import time

import aiosqlite
import pytest


@pytest.mark.asyncio
async def test_code_execute_blocks_ast_bypass_patterns():
    from backend.tools.tool_executor import _code_execute

    blocked_import = await _code_execute("import  os\nprint('x')")
    blocked_dynamic = await _code_execute(
        "import importlib\nimportlib.import_module('os')\nprint('x')"
    )

    assert blocked_import == "Blocked import: os"
    assert blocked_dynamic == "Blocked import: importlib"


@pytest.mark.asyncio
async def test_rlhf_converter_uses_feedback_response_ids(tmp_path):
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
            "CREATE TABLE conversation_turns (response_id TEXT, user_msg TEXT, assistant_msg TEXT, timestamp REAL)"
        )
        await db.executemany(
            "INSERT INTO conversation_turns VALUES (?, ?, ?, ?)",
            [
                ("resp-good", "good prompt", "good response with enough words to be usable in a preference pair", time.time()),
                ("resp-bad", "bad prompt", "bad response with enough words to also be usable here", time.time()),
                ("unrelated", "noise", "unrelated conversation turn that should not be selected", time.time()),
            ],
        )
        await db.commit()

    converter = FeedbackToRLHFConverter(str(feedback_db), str(conv_db))
    pairs = await converter.build_pairs(min_pairs=1)

    assert len(pairs) == 1
    assert pairs[0]["prompt"] == "good prompt"
    assert pairs[0]["chosen"].startswith("good response")
    assert pairs[0]["rejected"].startswith("bad response")


@pytest.mark.asyncio
async def test_learning_dataset_builder_uses_matching_response_id(tmp_path):
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
            "CREATE TABLE conversation_turns (response_id TEXT, user_msg TEXT, assistant_msg TEXT)"
        )
        await db.executemany(
            "INSERT INTO conversation_turns VALUES (?, ?, ?)",
            [
                ("resp-1", "matched prompt", "matched answer"),
                ("resp-2", "wrong prompt", "wrong answer"),
            ],
        )
        await db.commit()

    builder = DatasetBuilder(Cfg())
    count = await builder.build_from_feedback(str(feedback_db), str(conv_db))

    assert count == 1
    files = list((tmp_path / "training").glob("*.jsonl"))
    assert len(files) == 1
    rows = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert rows == [
        {
            "instruction": "matched prompt",
            "input": "",
            "output": "matched answer",
            "score": 5,
            "timestamp": rows[0]["timestamp"],
        }
    ]


def test_task_queue_purges_completed_tasks():
    from backend.distributed.task_queue import AsyncTaskQueue, Task, TaskStatus

    queue = AsyncTaskQueue(max_workers=1, retention_s=0)
    queue._tasks["done-task"] = Task(
        task_id="done-task",
        name="done-task",
        status=TaskStatus.DONE,
        ended_at=time.time() - 5,
    )

    queue.stats()

    assert "done-task" not in queue._tasks


def test_model_registry_requires_real_benchmark_scores(tmp_path):
    from backend.intelligence.model_registry import ModelRegistry

    class Cfg:
        enabled = True
        registry_path = str(tmp_path / "registry.json")
        benchmark_on_load = False

    registry = ModelRegistry(Cfg(), model_loader=None)
    registry.register("model-a", tasks=["chat"])

    assert registry.best_for_task("chat") is None


def test_production_rejects_default_secret_key():
    from backend.config.settings import AppSettings, SecuritySettings, ServerSettings

    with pytest.raises(ValueError):
        AppSettings(
            server=ServerSettings(environment="production"),
            security=SecuritySettings(secret_key="change-me"),
        )


def test_semantic_graph_persists_as_json(tmp_path):
    from backend.memory.advanced_memory import SemanticGraph

    path = tmp_path / "graph.json"
    graph = SemanticGraph(str(path))
    graph.update("Python uses FastAPI and SQLite")
    graph.save()

    data = json.loads(path.read_text())
    assert "nodes" in data
    assert "edges" in data
