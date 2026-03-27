"""Minimal SQLite-backed memory service for stable default mode."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite

from backend.config.settings import MemorySettings
from backend.models.schemas import MemoryEntry, MemorySearchRequest, MemorySearchResponse, MemoryStoreRequest


class SimpleMemoryService:
    CONV_TABLE = "simple_conversation_turns"
    MEM_TABLE = "simple_memory_entries"

    def __init__(self, cfg: MemorySettings) -> None:
        self.cfg = cfg
        self.db_path = Path(cfg.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self.db_path.as_posix())
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS {self.CONV_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_text TEXT NOT NULL,
                assistant_text TEXT NOT NULL,
                response_id TEXT,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS {self.MEM_TABLE} (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                content TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                priority REAL NOT NULL DEFAULT 1.0,
                reinforced REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_simple_conv_session_created
                ON {self.CONV_TABLE}(session_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_simple_mem_session_created
                ON {self.MEM_TABLE}(session_id, created_at DESC);
            """
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def save_turn(self, session_id: str, user_text: str, assistant_text: str, response_id: str = "") -> None:
        db = self._require_db()
        await db.execute(
            f"""
            INSERT INTO {self.CONV_TABLE} (session_id, user_text, assistant_text, response_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, user_text, assistant_text, response_id or None, time.time()),
        )
        await db.commit()

    async def get_context(self, session_id: str, prompt: str) -> list[dict[str, str]]:
        del prompt
        db = self._require_db()
        limit = max(1, self.cfg.context_window)
        async with db.execute(
            f"""
            SELECT user_text, assistant_text
            FROM {self.CONV_TABLE}
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        rows.reverse()
        return [{"user": row["user_text"], "assistant": row["assistant_text"]} for row in rows]

    async def get_history(self, session_id: str, limit: int = 20) -> list[dict[str, str]]:
        db = self._require_db()
        async with db.execute(
            f"""
            SELECT user_text, assistant_text, response_id, created_at
            FROM {self.CONV_TABLE}
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, max(1, limit)),
        ) as cursor:
            rows = await cursor.fetchall()
        rows.reverse()
        return [
            {
                "user": row["user_text"],
                "assistant": row["assistant_text"],
                "response_id": row["response_id"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def clear_history(self, session_id: str) -> None:
        db = self._require_db()
        await db.execute(f"DELETE FROM {self.CONV_TABLE} WHERE session_id = ?", (session_id,))
        await db.commit()

    async def search(self, req: MemorySearchRequest) -> MemorySearchResponse:
        db = self._require_db()
        query = f"%{req.query.strip()}%"
        sql = f"""
            SELECT id, content, priority, reinforced, created_at
            FROM {self.MEM_TABLE}
            WHERE content LIKE ?
        """
        params: list[Any] = [query]
        if req.session_id:
            sql += " AND session_id = ?"
            params.append(req.session_id)
        sql += " ORDER BY (priority + reinforced) DESC, created_at DESC LIMIT ?"
        params.append(max(1, req.top_k))
        async with db.execute(sql, tuple(params)) as cursor:
            rows = await cursor.fetchall()
        entries = [
            MemoryEntry(
                id=row["id"],
                content=row["content"],
                score=round(float(row["priority"] + row["reinforced"]), 2),
                priority=float(row["priority"]),
                source="manual",
                timestamp=float(row["created_at"]),
            )
            for row in rows
        ]
        return MemorySearchResponse(entries=entries, query=req.query, total_found=len(entries))

    async def store(self, req: MemoryStoreRequest) -> str:
        db = self._require_db()
        entry_id = uuid.uuid4().hex[:8]
        await db.execute(
            f"""
            INSERT INTO {self.MEM_TABLE} (id, session_id, content, tags_json, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                req.session_id,
                req.content,
                json.dumps(req.tags),
                req.priority,
                time.time(),
            ),
        )
        await db.commit()
        return entry_id

    async def list(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        db = self._require_db()
        async with db.execute(
            f"""
            SELECT id, content, tags_json, priority, reinforced, created_at
            FROM {self.MEM_TABLE}
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, max(1, limit)),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "content": row["content"],
                "tags": json.loads(row["tags_json"] or "[]"),
                "priority": float(row["priority"]),
                "score": round(float(row["priority"] + row["reinforced"]), 2),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def delete(self, entry_id: str) -> bool:
        db = self._require_db()
        cursor = await db.execute(f"DELETE FROM {self.MEM_TABLE} WHERE id = ?", (entry_id,))
        await db.commit()
        return cursor.rowcount > 0

    async def reinforce(self, entry_id: str, boost: float = 0.1) -> None:
        db = self._require_db()
        await db.execute(
            f"UPDATE {self.MEM_TABLE} SET reinforced = reinforced + ? WHERE id = ?",
            (boost, entry_id),
        )
        await db.commit()

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SimpleMemoryService not initialized")
        return self._db
