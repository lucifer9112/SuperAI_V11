"""
SuperAI V11 — backend/memory/memory_v9.py

Enhanced MemoryService with:
  - Priority scoring  (important memories ranked higher)
  - Temporal decay    (old memories fade unless reinforced)
  - Smart retrieval   (combines recency + relevance + priority)
  - Context-aware recall (boost memories matching current task)
  - Cleanup scheduler (prune stale low-priority memories)
"""
from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
from loguru import logger

from backend.config.settings import MemorySettings
from backend.models.schemas import (
    MemoryEntry, MemorySearchRequest, MemorySearchResponse, MemoryStoreRequest,
)


def _decay_factor(timestamp: float, decay_days: int) -> float:
    """Exponential decay: factor = e^(-age_days / decay_days)."""
    age_days = (time.time() - timestamp) / 86400
    return math.exp(-age_days / max(decay_days, 1))


class MemoryServiceV10:
    """
    Two-tier memory with priority scoring and temporal decay.

    Tier 1 — SQLite:  conversation history + explicit facts
    Tier 2 — FAISS:   semantic vector index for retrieval
    """

    def __init__(self, cfg: MemorySettings) -> None:
        self.cfg         = cfg
        self._db: Optional[aiosqlite.Connection] = None
        self._embed      = None
        self._index      = None
        self._id_map: Dict[int, str] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    # ── Lifecycle ─────────────────────────────────────────────────

    async def init(self) -> None:
        db_path = Path(self.cfg.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(str(db_path))
        self._db.row_factory = aiosqlite.Row
        await self._create_tables()
        await self._init_vector_store()

        # Start background cleanup
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("MemoryServiceV10 ready", db=str(db_path))

    async def close(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._db:
            await self._db.close()

    # ── Conversation history ──────────────────────────────────────

    async def save_turn(
        self, session_id: str, user_msg: str, assistant_msg: str,
        priority: float = 1.0,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO conversation_turns
              (session_id, user_msg, assistant_msg, timestamp, priority)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, user_msg, assistant_msg, time.time(), priority),
        )
        await self._db.commit()

        if self._embed and self._index is not None:
            await self._embed_and_index(
                content=f"Q: {user_msg}\nA: {assistant_msg}",
                session_id=session_id,
                source="conversation",
                priority=priority,
            )

    async def get_context(self, session_id: str, prompt: str) -> List[Dict[str, str]]:
        """Smart context: recent turns + semantically similar."""
        recent = await self.get_history(session_id, limit=self.cfg.context_window)

        if self._embed and self._index is not None and self._index.ntotal > 0:
            similar = await self._semantic_recall(prompt, session_id, top_k=3)
            # Merge: deduplicate by content
            seen = {t["user"] for t in recent}
            for s in similar:
                if s["user"] not in seen:
                    recent.append(s)
                    seen.add(s["user"])

        return recent[-self.cfg.context_window:]

    async def get_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        cur = await self._db.execute(
            """
            SELECT user_msg, assistant_msg, priority
            FROM conversation_turns
            WHERE session_id = ?
            ORDER BY timestamp DESC LIMIT ?
            """,
            (session_id, limit),
        )
        rows = await cur.fetchall()
        return [{"user": r["user_msg"], "assistant": r["assistant_msg"]} for r in reversed(rows)]

    async def clear_history(self, session_id: str) -> None:
        await self._db.execute(
            "DELETE FROM conversation_turns WHERE session_id = ?", (session_id,)
        )
        await self._db.commit()

    # ── Semantic memory ───────────────────────────────────────────

    async def search(self, req: MemorySearchRequest) -> MemorySearchResponse:
        if not self._embed or self._index is None or self._index.ntotal == 0:
            return MemorySearchResponse(query=req.query, entries=[])

        import numpy as np
        emb = await asyncio.to_thread(
            lambda: self._embed.encode([req.query], normalize_embeddings=True).astype("float32")
        )
        distances, indices = self._index.search(emb, req.top_k * 2)

        results: List[MemoryEntry] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            entry_id = self._id_map.get(idx)
            if not entry_id:
                continue
            row = await self._get_memory_row(entry_id)
            if not row:
                continue
            decay = _decay_factor(row["timestamp"], self.cfg.priority_decay_days)
            score = float(1 - dist) * float(row["priority"]) * decay
            results.append(MemoryEntry(
                id=entry_id,
                content=row["content"],
                score=round(score, 4),
                priority=float(row["priority"]),
                timestamp=str(row["timestamp"]),
                source=row["source"],
                decay=round(decay, 4),
            ))

        # Sort by combined score, limit to top_k
        results.sort(key=lambda e: e.score, reverse=True)
        return MemorySearchResponse(query=req.query, entries=results[:req.top_k])

    async def store(self, req: MemoryStoreRequest) -> str:
        entry_id = str(uuid.uuid4())
        await self._db.execute(
            """
            INSERT INTO memories (id, content, session_id, tags, timestamp, source, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_id, req.content, req.session_id,
             json.dumps(req.tags), time.time(), "user", req.priority),
        )
        await self._db.commit()

        if self._embed and self._index is not None:
            await self._embed_and_index(
                content=req.content, session_id=req.session_id or "",
                source="user", priority=req.priority, entry_id=entry_id,
            )
        return entry_id

    async def list(self, session_id: str, limit: int = 20) -> List[Dict]:
        cur = await self._db.execute(
            """
            SELECT id, content, tags, timestamp, source, priority
            FROM memories WHERE session_id = ?
            ORDER BY priority DESC, timestamp DESC LIMIT ?
            """,
            (session_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def delete(self, entry_id: str) -> bool:
        cur = await self._db.execute(
            "DELETE FROM memories WHERE id = ?", (entry_id,)
        )
        await self._db.commit()
        return cur.rowcount > 0

    async def search_by_tag(self, tag: str, top_k: int = 5) -> List[MemoryEntry]:
        cur = await self._db.execute(
            "SELECT * FROM memories WHERE tags LIKE ? ORDER BY priority DESC LIMIT ?",
            (f"%{tag}%", top_k),
        )
        rows = await cur.fetchall()
        return [
            MemoryEntry(
                id=r["id"], content=r["content"],
                score=1.0, priority=r["priority"],
                timestamp=str(r["timestamp"]), source=r["source"],
            )
            for r in rows
        ]

    async def reinforce(self, entry_id: str, boost: float = 0.1) -> None:
        """Boost priority of a memory (positive reinforcement)."""
        await self._db.execute(
            "UPDATE memories SET priority = MIN(2.0, priority + ?) WHERE id = ?",
            (boost, entry_id),
        )
        await self._db.commit()

    # ── Internals ─────────────────────────────────────────────────

    async def _create_tables(self) -> None:
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id    TEXT    NOT NULL,
                user_msg      TEXT    NOT NULL,
                assistant_msg TEXT    NOT NULL,
                timestamp     REAL    NOT NULL,
                priority      REAL    DEFAULT 1.0
            );
            CREATE INDEX IF NOT EXISTS idx_turns_session
                ON conversation_turns(session_id, timestamp);

            CREATE TABLE IF NOT EXISTS memories (
                id         TEXT PRIMARY KEY,
                content    TEXT NOT NULL,
                session_id TEXT,
                tags       TEXT DEFAULT '[]',
                timestamp  REAL NOT NULL,
                source     TEXT DEFAULT 'user',
                priority   REAL DEFAULT 1.0
            );
            CREATE INDEX IF NOT EXISTS idx_memories_session
                ON memories(session_id, priority);
        """)
        await self._db.commit()

    async def _init_vector_store(self) -> None:
        try:
            import faiss
            from sentence_transformers import SentenceTransformer

            def _load():
                m   = SentenceTransformer(self.cfg.embedding_model)
                dim = m.get_sentence_embedding_dimension()
                idx = faiss.IndexFlatIP(dim)
                return m, idx

            self._embed, self._index = await asyncio.to_thread(_load)
            logger.info("V10 vector store ready", model=self.cfg.embedding_model)
        except ImportError as e:
            logger.warning("Vector store disabled", error=str(e))

    async def _embed_and_index(
        self, content: str, session_id: str, source: str,
        priority: float = 1.0, entry_id: Optional[str] = None,
    ) -> None:
        import numpy as np
        emb = await asyncio.to_thread(
            lambda: self._embed.encode([content], normalize_embeddings=True).astype("float32")
        )
        idx = self._index.ntotal
        self._index.add(emb)
        self._id_map[idx] = entry_id or f"turn_{idx}"

    async def _semantic_recall(
        self, query: str, session_id: str, top_k: int
    ) -> List[Dict[str, str]]:
        """Return turns semantically similar to query."""
        result = await self.search(MemorySearchRequest(
            query=query, session_id=session_id, top_k=top_k
        ))
        return [
            {"user": e.content, "assistant": ""}
            for e in result.entries
            if e.source == "conversation"
        ]

    async def _get_memory_row(self, entry_id: str) -> Optional[Any]:
        if entry_id.startswith("turn_"):
            return None
        cur = await self._db.execute(
            "SELECT * FROM memories WHERE id = ?", (entry_id,)
        )
        return await cur.fetchone()

    async def _cleanup_loop(self) -> None:
        """Background task: prune stale low-priority memories every 6 hours."""
        while True:
            try:
                await asyncio.sleep(6 * 3600)
                await self._prune_stale()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Memory cleanup error", error=str(e))

    async def _prune_stale(self) -> None:
        cutoff = time.time() - (self.cfg.priority_decay_days * 86400)
        cur = await self._db.execute(
            "DELETE FROM memories WHERE timestamp < ? AND priority < 0.3",
            (cutoff,),
        )
        await self._db.commit()
        if cur.rowcount:
            logger.info("Memory pruned", removed=cur.rowcount)
