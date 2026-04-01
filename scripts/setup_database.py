"""Bootstrap the local SuperAI V11 SQLite and runtime data layout."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config.settings import settings

DATA_DIR = ROOT_DIR / "data"


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _connect(path: Path) -> sqlite3.Connection:
    _ensure_dir(path.parent)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _init_memory_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS simple_conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_text TEXT NOT NULL,
                assistant_text TEXT NOT NULL,
                response_id TEXT,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS simple_memory_entries (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                content TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                priority REAL NOT NULL DEFAULT 1.0,
                reinforced REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_simple_conv_session_created
                ON simple_conversation_turns(session_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_simple_mem_session_created
                ON simple_memory_entries(session_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_msg TEXT NOT NULL,
                assistant_msg TEXT NOT NULL,
                timestamp REAL NOT NULL,
                priority REAL DEFAULT 1.0,
                response_id TEXT
            );

            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                session_id TEXT,
                tags TEXT DEFAULT '[]',
                timestamp REAL NOT NULL,
                source TEXT DEFAULT 'user',
                priority REAL DEFAULT 1.0
            );

            CREATE INDEX IF NOT EXISTS idx_memories_session
                ON memories(session_id, priority);
            """
        )
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(conversation_turns)").fetchall()
        }
        if "response_id" not in columns:
            conn.execute("ALTER TABLE conversation_turns ADD COLUMN response_id TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_turns_session ON conversation_turns(session_id, timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_turns_response ON conversation_turns(response_id)"
        )
        conn.commit()


def _init_feedback_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                response_id TEXT NOT NULL,
                session_id TEXT,
                score INTEGER NOT NULL,
                comment TEXT DEFAULT '',
                timestamp REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_feedback_response_id
                ON feedback(response_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_session_timestamp
                ON feedback(session_id, timestamp DESC);
            """
        )
        conn.commit()


def _init_episodic_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_msg TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                emotion TEXT DEFAULT 'neutral',
                timestamp REAL NOT NULL,
                tags TEXT DEFAULT '[]',
                importance REAL DEFAULT 1.0
            );

            CREATE INDEX IF NOT EXISTS idx_ep_session
                ON episodes(session_id, timestamp);
            """
        )
        conn.commit()


def _init_improvement_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS failures (
                failure_id TEXT PRIMARY KEY,
                session_id TEXT,
                user_prompt TEXT,
                ai_response TEXT,
                failure_type TEXT,
                severity REAL,
                root_cause TEXT,
                suggestion TEXT,
                timestamp REAL
            );

            CREATE TABLE IF NOT EXISTS improvement_logs (
                log_id TEXT PRIMARY KEY,
                failure_type TEXT,
                pattern TEXT,
                suggestion TEXT,
                priority TEXT,
                count INTEGER DEFAULT 1,
                timestamp REAL
            );
            """
        )
        conn.commit()


def _init_rlhf_log_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rlhf_runs (
                run_id TEXT PRIMARY KEY,
                method TEXT,
                model TEXT,
                n_pairs INT,
                status TEXT,
                metrics TEXT,
                t_start REAL,
                t_end REAL,
                checkpoint TEXT
            );
            """
        )
        conn.commit()


def _ensure_json(path: Path, payload: object) -> None:
    if path.exists():
        return
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    runtime_dirs = [
        DATA_DIR,
        DATA_DIR / "uploads",
        DATA_DIR / "custom_skills",
        DATA_DIR / "training",
        DATA_DIR / "lora_checkpoints",
        DATA_DIR / "rlhf_checkpoints",
        DATA_DIR / "improvement_logs",
        DATA_DIR / "security_logs",
        DATA_DIR / "reward_model",
    ]
    for path in runtime_dirs:
        _ensure_dir(path)

    memory_db = _resolve_path(settings.memory.db_path)
    legacy_memory_db = DATA_DIR / "superai_v11.db"
    feedback_db = _resolve_path(settings.feedback.store_path)
    episodic_db = DATA_DIR / "episodic.db"
    improvements_db = DATA_DIR / "improvements.db"
    rlhf_logs_db = DATA_DIR / "rlhf_logs.db"

    for path in {memory_db, legacy_memory_db}:
        _init_memory_db(path)
    _init_feedback_db(feedback_db)
    _init_episodic_db(episodic_db)
    _init_improvement_db(improvements_db)
    _init_rlhf_log_db(rlhf_logs_db)

    _ensure_json(DATA_DIR / "knowledge_graph.json", {"nodes": {}, "edges": []})
    _ensure_json(DATA_DIR / "model_registry.json", {})

    print("Initialized runtime directories and SQLite databases:")
    for path in [
        memory_db,
        legacy_memory_db,
        feedback_db,
        episodic_db,
        improvements_db,
        rlhf_logs_db,
        DATA_DIR / "knowledge_graph.json",
        DATA_DIR / "model_registry.json",
    ]:
        print(f" - {path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
