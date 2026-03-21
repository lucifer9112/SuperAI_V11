"""
SuperAI V11 — backend/agents/coordinator.py

Agent Coordination System (NEW in V10).

Architecture:
  AgentCoordinator
    ├── ContextBus         — shared state between agents
    ├── TaskDelegator      — route sub-tasks to specialized agents
    ├── ConflictResolver   — resolve contradictory agent outputs
    └── AgentRegistry      — track all active agent runs

Key features:
  - Agents can share context with each other via ContextBus
  - Tasks can be delegated to the best-suited sub-agent
  - Conflicting answers are reconciled by a resolver agent
  - All agent activity is logged for the monitoring dashboard
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


# ── Context Bus ───────────────────────────────────────────────────

@dataclass
class ContextEntry:
    agent_id:  str
    key:       str
    value:     Any
    timestamp: float = field(default_factory=time.time)
    ttl:       int   = 3600   # seconds


class ContextBus:
    """
    Shared in-memory context between agents.
    Agents can publish facts and subscribe to context from other agents.
    TTL-based expiry prevents stale data.
    """

    def __init__(self, ttl: int = 3600) -> None:
        self._store: Dict[str, ContextEntry] = {}
        self._default_ttl = ttl
        self._lock = asyncio.Lock()

    async def publish(self, agent_id: str, key: str, value: Any) -> None:
        async with self._lock:
            full_key = f"{agent_id}:{key}"
            self._store[full_key] = ContextEntry(
                agent_id=agent_id, key=key, value=value, ttl=self._default_ttl
            )
            logger.debug("ContextBus publish", agent=agent_id, key=key)

    async def get(self, key: str, agent_id: Optional[str] = None) -> Optional[Any]:
        async with self._lock:
            self._evict()
            if agent_id:
                entry = self._store.get(f"{agent_id}:{key}")
                return entry.value if entry else None
            # Search across all agents
            for full_key, entry in self._store.items():
                if full_key.endswith(f":{key}"):
                    return entry.value
            return None

    async def get_all(self) -> Dict[str, Any]:
        """Return all non-expired context as flat dict."""
        async with self._lock:
            self._evict()
            return {k: e.value for k, e in self._store.items()}

    async def clear_agent(self, agent_id: str) -> None:
        async with self._lock:
            keys = [k for k in self._store if k.startswith(f"{agent_id}:")]
            for k in keys:
                del self._store[k]

    def _evict(self) -> None:
        now = time.time()
        expired = [
            k for k, e in self._store.items()
            if (now - e.timestamp) > e.ttl
        ]
        for k in expired:
            del self._store[k]


# ── Task Delegator ────────────────────────────────────────────────

class TaskDelegator:
    """
    Routes sub-tasks to the most appropriate agent type.
    Uses keyword-based routing (same pattern as TaskRouter).
    """

    _DELEGATION_MAP = {
        "search":   ["search_web", "fetch_url"],
        "code":     ["run_code",   "review_code"],
        "math":     ["calculate",  "solve_equation"],
        "file":     ["read_file",  "parse_document"],
        "memory":   ["store_fact", "recall_fact"],
    }

    def delegate(self, task: str) -> str:
        """Return the best agent type for a task description."""
        task_lower = task.lower()
        for agent_type, keywords in self._DELEGATION_MAP.items():
            if any(kw in task_lower for kw in keywords):
                return agent_type
        return "general"


# ── Conflict Resolver ─────────────────────────────────────────────

class ConflictResolver:
    """
    Reconcile contradictory outputs from multiple agents.
    Strategy: majority vote > confidence score > recency
    """

    def resolve(self, answers: List[Dict[str, Any]]) -> str:
        """
        answers: list of {"answer": str, "confidence": float, "agent_id": str}
        Returns the best single answer.
        """
        if not answers:
            return ""
        if len(answers) == 1:
            return answers[0]["answer"]

        # Sort by confidence descending
        sorted_answers = sorted(answers, key=lambda x: x.get("confidence", 0.5), reverse=True)

        # If top confidence is significantly higher, use it
        if len(sorted_answers) >= 2:
            top_conf = sorted_answers[0].get("confidence", 0.5)
            second   = sorted_answers[1].get("confidence", 0.5)
            if top_conf - second > 0.2:
                return sorted_answers[0]["answer"]

        # Otherwise vote by similarity (simplified: return longest non-empty)
        best = max(answers, key=lambda x: len(x.get("answer", "")))
        return best["answer"]


# ── Agent Registry ────────────────────────────────────────────────

@dataclass
class AgentRecord:
    agent_id:   str
    goal:       str
    status:     str       = "running"
    started_at: float     = field(default_factory=time.time)
    ended_at:   Optional[float] = None
    result:     Optional[str]   = None


class AgentRegistry:
    """Track all agent runs for the monitoring dashboard."""

    def __init__(self) -> None:
        self._records: Dict[str, AgentRecord] = {}

    def register(self, agent_id: str, goal: str) -> None:
        self._records[agent_id] = AgentRecord(agent_id=agent_id, goal=goal)

    def update(self, agent_id: str, status: str, result: Optional[str] = None) -> None:
        rec = self._records.get(agent_id)
        if rec:
            rec.status   = status
            rec.ended_at = time.time()
            rec.result   = result

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        return self._records.get(agent_id)

    def list_active(self) -> List[AgentRecord]:
        return [r for r in self._records.values() if r.status == "running"]

    def list_all(self, limit: int = 50) -> List[Dict]:
        records = sorted(self._records.values(),
                         key=lambda r: r.started_at, reverse=True)[:limit]
        return [
            {
                "agent_id":  r.agent_id,
                "goal":      r.goal[:80],
                "status":    r.status,
                "started":   r.started_at,
                "duration_s": round((r.ended_at or time.time()) - r.started_at, 1),
            }
            for r in records
        ]


# ── Main Coordinator ──────────────────────────────────────────────

class AgentCoordinator:
    """
    Top-level coordinator. Injected into AgentService.
    Provides context bus, delegation, conflict resolution, and registry.
    """

    def __init__(self, context_ttl: int = 3600) -> None:
        self.context   = ContextBus(ttl=context_ttl)
        self.delegator = TaskDelegator()
        self.resolver  = ConflictResolver()
        self.registry  = AgentRegistry()
        logger.info("AgentCoordinator V10 ready")

    async def start_run(self, goal: str) -> str:
        agent_id = str(uuid.uuid4())[:10]
        self.registry.register(agent_id, goal)
        logger.info("Agent run started", agent_id=agent_id, goal=goal[:60])
        return agent_id

    async def finish_run(
        self, agent_id: str, status: str, result: Optional[str] = None
    ) -> None:
        self.registry.update(agent_id, status, result)
        await self.context.clear_agent(agent_id)
        logger.info("Agent run finished", agent_id=agent_id, status=status)

    async def share_context(self, agent_id: str, key: str, value: Any) -> None:
        await self.context.publish(agent_id, key, value)

    async def read_context(self, key: str) -> Optional[Any]:
        return await self.context.get(key)
