"""
SuperAI V11 — backend/intelligence/self_improvement.py

FEATURE 6: Self-Improvement Loop

The AI tracks its own failures and generates improvement suggestions:
  1. FailureDetector  — identifies low-quality or failed responses
  2. FailureAnalyzer  — LLM-based root cause analysis
  3. ImprovementLogger — stores structured improvement logs
  4. PromptOptimizer  — auto-generates better system prompts

Failure signals:
  - User rating <= 2 stars
  - Model inference timeout
  - Reflection engine flagged low confidence
  - User follow-up correction ("No, that's wrong")
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
from loguru import logger


# ── Data structures ───────────────────────────────────────────────

@dataclass
class FailureRecord:
    failure_id:    str
    session_id:    str
    user_prompt:   str
    ai_response:   str
    failure_type:  str       # "low_rating" | "timeout" | "low_confidence" | "correction"
    severity:      float     # 0.0 – 1.0
    timestamp:     float = field(default_factory=time.time)
    root_cause:    str   = ""
    suggestion:    str   = ""


@dataclass
class ImprovementLog:
    log_id:        str
    failure_type:  str
    pattern:       str       # what kind of failures keep recurring
    suggestion:    str       # concrete improvement action
    priority:      str       # "high" | "medium" | "low"
    count:         int       = 1
    timestamp:     float     = field(default_factory=time.time)


# ── Failure Detector ──────────────────────────────────────────────

class FailureDetector:
    """Detects failure signals from various sources."""

    CORRECTION_PATTERNS = [
        r"no[,.]?\s+that'?s?\s+wrong",
        r"that'?s?\s+incorrect",
        r"you'?re?\s+wrong",
        r"not\s+quite",
        r"that's?\s+not\s+right",
        r"^\s*actually[,:]\s+(?:that'?s|that is|the answer|it|you)",
        r"correction:",
    ]

    def __init__(self) -> None:
        import re
        self._correction_re = [
            re.compile(p, re.IGNORECASE) for p in self.CORRECTION_PATTERNS
        ]

    def detect_from_rating(self, score: int) -> Optional[FailureRecord]:
        if score > 2:
            return None
        return FailureRecord(
            failure_id   = str(uuid.uuid4())[:8],
            session_id   = "",
            user_prompt  = "",
            ai_response  = "",
            failure_type = "low_rating",
            severity     = 1.0 - (score - 1) / 4.0,
        )

    def detect_from_confidence(
        self, confidence: float, prompt: str, response: str, session_id: str
    ) -> Optional[FailureRecord]:
        if confidence >= 0.4:
            return None
        return FailureRecord(
            failure_id   = str(uuid.uuid4())[:8],
            session_id   = session_id,
            user_prompt  = prompt,
            ai_response  = response,
            failure_type = "low_confidence",
            severity     = 1.0 - confidence,
        )

    def detect_correction(
        self, user_msg: str, session_id: str
    ) -> Optional[FailureRecord]:
        for pat in self._correction_re:
            if pat.search(user_msg):
                return FailureRecord(
                    failure_id   = str(uuid.uuid4())[:8],
                    session_id   = session_id,
                    user_prompt  = user_msg,
                    ai_response  = "",
                    failure_type = "correction",
                    severity     = 0.8,
                )
        return None


# ── Failure Analyzer ──────────────────────────────────────────────

class FailureAnalyzer:
    """
    Uses LLM to analyze failure root causes and generate suggestions.
    """

    def __init__(self, model_loader) -> None:
        self._models = model_loader

    async def analyze(
        self, failure: FailureRecord, model_name: str
    ) -> FailureRecord:
        if not failure.user_prompt:
            return failure

        prompt = (
            f"You are an AI quality analyst. Analyze this AI response failure:\n\n"
            f"User asked: {failure.user_prompt[:300]}\n"
            f"AI responded: {failure.ai_response[:300]}\n"
            f"Failure type: {failure.failure_type}\n\n"
            f"Provide:\n"
            f"ROOT_CAUSE: <one sentence>\n"
            f"SUGGESTION: <concrete improvement action>"
        )

        try:
            analysis, _ = await asyncio.wait_for(
                self._models.infer(model_name, prompt, max_tokens=200, temperature=0.3),
                timeout=20,
            )
            failure.root_cause = self._extract("ROOT_CAUSE", analysis)
            failure.suggestion = self._extract("SUGGESTION", analysis)
        except Exception as e:
            logger.warning("Failure analysis error", error=str(e))

        return failure

    @staticmethod
    def _extract(key: str, text: str) -> str:
        import re
        m = re.search(rf"{key}:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        return m.group(1).strip() if m else ""


# ── Improvement Logger ────────────────────────────────────────────

class ImprovementLogger:
    """
    Persists failure records and improvement logs to SQLite.
    Provides pattern analysis across failures.
    """

    def __init__(self, db_path: str, log_dir: str) -> None:
        self.db_path = db_path
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS failures (
                failure_id   TEXT PRIMARY KEY,
                session_id   TEXT,
                user_prompt  TEXT,
                ai_response  TEXT,
                failure_type TEXT,
                severity     REAL,
                root_cause   TEXT,
                suggestion   TEXT,
                timestamp    REAL
            );
            CREATE TABLE IF NOT EXISTS improvement_logs (
                log_id       TEXT PRIMARY KEY,
                failure_type TEXT,
                pattern      TEXT,
                suggestion   TEXT,
                priority     TEXT,
                count        INTEGER DEFAULT 1,
                timestamp    REAL
            );
        """)
        await self._db.commit()

    async def log_failure(self, failure: FailureRecord) -> None:
        if not self._db:
            return
        await self._db.execute(
            "INSERT OR IGNORE INTO failures VALUES (?,?,?,?,?,?,?,?,?)",
            (failure.failure_id, failure.session_id,
             failure.user_prompt[:500], failure.ai_response[:500],
             failure.failure_type, failure.severity,
             failure.root_cause, failure.suggestion, failure.timestamp),
        )
        await self._db.commit()

    async def get_failure_patterns(self, min_count: int = 3) -> List[Dict]:
        """Find recurring failure patterns."""
        if not self._db:
            return []
        cur = await self._db.execute(
            """
            SELECT failure_type, COUNT(*) as cnt, AVG(severity) as avg_sev
            FROM failures
            WHERE timestamp > ?
            GROUP BY failure_type
            HAVING cnt >= ?
            ORDER BY cnt DESC
            """,
            (time.time() - 7 * 86400, min_count),
        )
        rows = await cur.fetchall()
        return [{"type": r[0], "count": r[1], "avg_severity": round(r[2], 2)} for r in rows]

    async def get_stats(self) -> Dict:
        if not self._db:
            return {}
        cur = await self._db.execute(
            "SELECT COUNT(*), AVG(severity) FROM failures WHERE timestamp > ?",
            (time.time() - 7 * 86400,)
        )
        row = await cur.fetchone()
        patterns = await self.get_failure_patterns(min_count=2)
        return {
            "failures_7d":    row[0] or 0,
            "avg_severity":   round(row[1] or 0, 2),
            "top_patterns":   patterns[:3],
        }

    async def close(self) -> None:
        if self._db:
            await self._db.close()


# ── Main Self-Improvement Engine ──────────────────────────────────

class SelfImprovementEngine:
    """
    Orchestrates failure detection, analysis, and improvement logging.
    Also generates prompt optimization suggestions.
    """

    def __init__(self, cfg, model_loader) -> None:
        self.cfg      = cfg
        self._enabled = getattr(cfg, "enabled", True)
        self._min_failures = getattr(cfg, "min_failures_to_analyze", 5)
        self._detector = FailureDetector()
        self._analyzer = FailureAnalyzer(model_loader)
        self._logger   = ImprovementLogger(
            db_path=getattr(cfg, "improvement_db_path", "data/improvements.db"),
            log_dir=getattr(cfg, "failure_log_path", "data/improvement_logs/"),
        )
        self._task: Optional[asyncio.Task] = None

    async def init(self) -> None:
        await self._logger.init()
        if self._enabled:
            interval = (getattr(self.cfg, "analysis_interval_hours", 12) if self.cfg else 12) * 3600
            self._task = asyncio.create_task(self._analysis_loop(interval))
        logger.info("SelfImprovementEngine ready")

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        await self._logger.close()

    async def record_low_rating(
        self, score: int, prompt: str, response: str, session_id: str,
        model_name: str = "",
    ) -> None:
        if not self._enabled or score > 2:
            return
        failure = self._detector.detect_from_rating(score)
        if failure:
            failure.session_id  = session_id
            failure.user_prompt = prompt
            failure.ai_response = response
            if model_name:
                failure = await self._analyzer.analyze(failure, model_name)
            await self._logger.log_failure(failure)

    async def record_low_confidence(
        self, confidence: float, prompt: str, response: str, session_id: str
    ) -> None:
        if not self._enabled:
            return
        failure = self._detector.detect_from_confidence(confidence, prompt, response, session_id)
        if failure:
            await self._logger.log_failure(failure)

    async def check_correction(self, user_msg: str, session_id: str) -> None:
        if not self._enabled:
            return
        failure = self._detector.detect_correction(user_msg, session_id)
        if failure:
            await self._logger.log_failure(failure)

    async def get_stats(self) -> Dict:
        return await self._logger.get_stats()

    async def suggest_improvements(self) -> List[str]:
        """Generate human-readable improvement suggestions."""
        patterns = await self._logger.get_failure_patterns(min_count=2)
        suggestions = []
        for p in patterns:
            if p["type"] == "low_confidence":
                suggestions.append(
                    f"Model uncertainty high ({p['count']} cases). "
                    f"Consider fine-tuning with more diverse data or lowering response max_tokens."
                )
            elif p["type"] == "low_rating":
                suggestions.append(
                    f"User satisfaction issues ({p['count']} cases). "
                    f"Review recent conversations — consider prompt template adjustments."
                )
            elif p["type"] == "correction":
                suggestions.append(
                    f"Factual correction pattern ({p['count']} cases). "
                    f"Recommend enabling RAG++ for grounded retrieval."
                )
        return suggestions

    async def _analysis_loop(self, interval: float) -> None:
        while True:
            try:
                await asyncio.sleep(interval)
                stats = await self.get_stats()
                if stats.get("failures_7d", 0) >= self._min_failures:
                    suggestions = await self.suggest_improvements()
                    for s in suggestions:
                        logger.warning("IMPROVEMENT_HINT", suggestion=s)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Improvement analysis error", error=str(e))
