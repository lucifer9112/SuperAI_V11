"""SuperAI V11 - backend/services/feedback_service.py."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Dict, Optional

import aiosqlite
from loguru import logger

from backend.config.settings import FeedbackSettings
from backend.models.schemas import FeedbackRequest, FeedbackResponse


class FeedbackService:
    def __init__(self, cfg: FeedbackSettings) -> None:
        self.cfg = cfg
        self._db: Optional[aiosqlite.Connection] = None
        self._total = 0

    async def init(self) -> None:
        if not self.cfg.enabled:
            return
        db_path = Path(self.cfg.store_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(db_path))
        await self._create_table()
        await self._load_recent_scores()
        logger.info("FeedbackService V10 ready")

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def record(self, req: FeedbackRequest) -> FeedbackResponse:
        if not self.cfg.enabled:
            return FeedbackResponse(recorded=False, response_id=req.response_id, score=req.score)

        if self._db is None:
            logger.warning("Feedback DB not initialized")
            return FeedbackResponse(recorded=False, response_id=req.response_id, score=req.score)

        if req.score < self.cfg.min_score or req.score > self.cfg.max_score:
            logger.warning(
                "Feedback score out of range",
                score=req.score,
                min_score=self.cfg.min_score,
                max_score=self.cfg.max_score,
            )
            return FeedbackResponse(recorded=False, response_id=req.response_id, score=req.score)

        feedback_id = str(uuid.uuid4())
        await self._db.execute(
            """
            INSERT INTO feedback
              (id, response_id, session_id, score, comment, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (feedback_id, req.response_id, req.session_id, req.score, req.comment, time.time()),
        )
        await self._db.commit()

        self._total += 1
        self._maybe_emit_retrain_hint()
        logger.info("Feedback stored", response_id=req.response_id, score=req.score)

        return FeedbackResponse(
            feedback_id=feedback_id[:8],
            response_id=req.response_id,
            score=req.score,
            recorded=True,
        )

    async def get_stats(self) -> Dict:
        if not self._db:
            return {}
        cursor = await self._db.execute(
            """
            SELECT
              COUNT(*) as total,
              AVG(score) as avg_score,
              SUM(CASE WHEN score <= 2 THEN 1 ELSE 0 END) as negative,
              SUM(CASE WHEN score >= 4 THEN 1 ELSE 0 END) as positive
            FROM feedback
            WHERE timestamp > ?
            """,
            (time.time() - 7 * 86400,),
        )
        row = await cursor.fetchone()
        return {
          "total_7d": row[0] or 0,
          "avg_score": round(row[1] or 0, 2),
          "negative_7d": row[2] or 0,
          "positive_7d": row[3] or 0,
          "total_all": self._total,
        }

    def total_count(self) -> int:
        return self._total

    async def _create_table(self) -> None:
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id          TEXT PRIMARY KEY,
                response_id TEXT NOT NULL,
                session_id  TEXT,
                score       INTEGER NOT NULL,
                comment     TEXT DEFAULT '',
                timestamp   REAL NOT NULL
            )
            """
        )
        await self._db.commit()

    async def _load_recent_scores(self) -> None:
        cursor = await self._db.execute("SELECT COUNT(*) FROM feedback")
        row = await cursor.fetchone()
        self._total = row[0] if row else 0

    def _maybe_emit_retrain_hint(self) -> None:
        if self._total % self.cfg.learning_threshold == 0 and self._total > 0:
            logger.warning(
                "RETRAIN_HINT: accumulated enough feedback for review",
                count=self._total,
                threshold=self.cfg.learning_threshold,
            )
