"""
SuperAI V11 — backend/memory/advanced_memory.py

FEATURE 3: Advanced Memory System (Human-like)

Three memory tiers:
  1. EpisodicMemory   — stores events (what happened, when, where, emotion)
  2. SemanticGraph    — knowledge graph of entities and relationships
  3. EmotionalMemory  — tags context with detected emotional state

All three are queried together by UnifiedMemoryRetriever which
combines results from V9 FAISS + episodic + graph + emotion context.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
from loguru import logger


# ── Emotion detector ──────────────────────────────────────────────

_EMOTION_PATTERNS: Dict[str, List[str]] = {
    "positive":   ["great", "excellent", "love", "awesome", "happy", "thanks", "perfect", "amazing"],
    "negative":   ["bad", "wrong", "error", "fail", "broken", "hate", "terrible", "awful", "bug"],
    "curious":    ["how", "why", "what", "explain", "understand", "learn", "curious", "tell me"],
    "frustrated": ["again", "still not", "doesn't work", "frustrated", "stuck", "keeps failing"],
    "urgent":     ["urgent", "asap", "immediately", "critical", "emergency", "now", "hurry"],
}


def detect_emotion(text: str) -> str:
    text_lower = text.lower()
    scores: Dict[str, int] = {e: 0 for e in _EMOTION_PATTERNS}
    for emotion, keywords in _EMOTION_PATTERNS.items():
        scores[emotion] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=lambda e: scores[e])
    return best if scores[best] > 0 else "neutral"


# ── Episodic Memory ───────────────────────────────────────────────

@dataclass
class Episode:
    id:          str
    session_id:  str
    user_msg:    str
    ai_response: str
    emotion:     str
    timestamp:   float
    tags:        List[str] = field(default_factory=list)
    importance:  float     = 1.0


class EpisodicMemory:
    """
    Stores discrete interaction events with emotional context.
    Queryable by time range, emotion, or keyword.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                user_msg    TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                emotion     TEXT DEFAULT 'neutral',
                timestamp   REAL NOT NULL,
                tags        TEXT DEFAULT '[]',
                importance  REAL DEFAULT 1.0
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_ep_session ON episodes(session_id, timestamp)"
        )
        await self._db.commit()
        logger.info("EpisodicMemory ready", db=self.db_path)

    async def store(
        self,
        session_id: str,
        user_msg: str,
        ai_response: str,
        tags: Optional[List[str]] = None,
        importance: float = 1.0,
    ) -> str:
        emotion = detect_emotion(user_msg)
        ep_id   = str(uuid.uuid4())[:10]
        await self._db.execute(
            "INSERT INTO episodes (id,session_id,user_msg,ai_response,emotion,timestamp,tags,importance) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (ep_id, session_id, user_msg, ai_response,
             emotion, time.time(), json.dumps(tags or []), importance),
        )
        await self._db.commit()
        return ep_id

    async def recall(
        self,
        session_id: str,
        emotion: Optional[str] = None,
        limit: int = 5,
    ) -> List[Episode]:
        if emotion:
            cur = await self._db.execute(
                "SELECT * FROM episodes WHERE session_id=? AND emotion=? "
                "ORDER BY timestamp DESC LIMIT ?",
                (session_id, emotion, limit),
            )
        else:
            cur = await self._db.execute(
                "SELECT * FROM episodes WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            )
        rows = await cur.fetchall()
        return [
            Episode(id=r["id"], session_id=r["session_id"],
                    user_msg=r["user_msg"], ai_response=r["ai_response"],
                    emotion=r["emotion"], timestamp=r["timestamp"],
                    tags=json.loads(r["tags"]), importance=r["importance"])
            for r in rows
        ]

    async def recall_by_keyword(self, keyword: str, limit: int = 5) -> List[Episode]:
        cur = await self._db.execute(
            "SELECT * FROM episodes WHERE user_msg LIKE ? OR ai_response LIKE ? "
            "ORDER BY importance DESC, timestamp DESC LIMIT ?",
            (f"%{keyword}%", f"%{keyword}%", limit),
        )
        rows = await cur.fetchall()
        return [
            Episode(id=r["id"], session_id=r["session_id"],
                    user_msg=r["user_msg"], ai_response=r["ai_response"],
                    emotion=r["emotion"], timestamp=r["timestamp"],
                    tags=json.loads(r["tags"]), importance=r["importance"])
            for r in rows
        ]

    async def close(self) -> None:
        if self._db:
            await self._db.close()


# ── Semantic Knowledge Graph ──────────────────────────────────────

@dataclass
class GraphNode:
    entity:     str
    node_type:  str   # "concept" | "person" | "technology" | "fact"
    mentions:   int   = 1
    first_seen: float = field(default_factory=time.time)


@dataclass
class GraphEdge:
    source:      str
    target:      str
    relation:    str
    weight:      float = 1.0
    last_seen:   float = field(default_factory=time.time)


class SemanticGraph:
    """
    Lightweight in-memory knowledge graph.
    Extracts entities and relations from conversations.
    Persisted to disk as JSON.
    """

    def __init__(self, graph_path: str, max_nodes: int = 10000) -> None:
        self.graph_path = Path(graph_path)
        self.max_nodes  = max_nodes
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge]      = []
        self._update_count: int = 0
        self._auto_save_interval: int = 10
        self._load()
        logger.info("SemanticGraph ready", nodes=len(self._nodes))

    def update(self, text: str) -> None:
        """Extract entities and add/update graph nodes + edges."""
        entities = self._extract_entities(text)
        for ent, etype in entities:
            ent_lower = ent.lower()
            if ent_lower in self._nodes:
                self._nodes[ent_lower].mentions += 1
            elif len(self._nodes) < self.max_nodes:
                self._nodes[ent_lower] = GraphNode(entity=ent, node_type=etype)

        # Add co-occurrence edges
        entity_list = [e[0].lower() for e in entities]
        for i in range(len(entity_list)):
            for j in range(i + 1, min(i + 3, len(entity_list))):
                self._add_edge(entity_list[i], entity_list[j], "co_occurs")

        # Auto-save periodically to prevent data loss
        self._update_count += 1
        if self._update_count % self._auto_save_interval == 0:
            self.save()

    def query(self, keyword: str, top_k: int = 5) -> List[Dict]:
        """Find entities related to keyword."""
        kw = keyword.lower()
        matches = [
            {"entity": n.entity, "type": n.node_type, "mentions": n.mentions}
            for key, n in self._nodes.items()
            if kw in key
        ]
        matches.sort(key=lambda x: x["mentions"], reverse=True)
        return matches[:top_k]

    def neighbors(self, entity: str, limit: int = 5) -> List[str]:
        """Return entities connected to a given entity."""
        ent = entity.lower()
        related = []
        for edge in self._edges:
            if edge.source == ent:
                related.append((edge.target, edge.weight))
            elif edge.target == ent:
                related.append((edge.source, edge.weight))
        related.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in related[:limit]]

    def save(self) -> None:
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "nodes": {key: asdict(node) for key, node in self._nodes.items()},
                "edges": [asdict(edge) for edge in self._edges],
            }
            self.graph_path.write_text(json.dumps(data), encoding="utf-8")
        except Exception as e:
            logger.warning("Graph save failed", error=str(e))

    def _load(self) -> None:
        if self.graph_path.exists():
            try:
                data = json.loads(self.graph_path.read_text(encoding="utf-8"))
                self._nodes = {
                    key: GraphNode(**value)
                    for key, value in data.get("nodes", {}).items()
                }
                self._edges = [GraphEdge(**value) for value in data.get("edges", [])]
            except Exception:
                pass

    def _add_edge(self, src: str, tgt: str, rel: str) -> None:
        for edge in self._edges:
            if edge.source == src and edge.target == tgt:
                edge.weight += 0.1
                edge.last_seen = time.time()
                return
        if len(self._edges) < self.max_nodes * 2:
            self._edges.append(GraphEdge(source=src, target=tgt, relation=rel))

    @staticmethod
    def _extract_entities(text: str) -> List[Tuple[str, str]]:
        """Simple heuristic entity extraction."""
        entities = []

        # Capitalized words = likely entities
        for word in re.findall(r'\b[A-Z][a-z]{2,}\b', text):
            entities.append((word, "concept"))

        # Tech keywords
        tech = re.findall(
            r'\b(Python|JavaScript|FastAPI|React|Docker|CUDA|GPU|API|LLM|AI|ML|'
            r'transformer|neural|model|database|SQLite|FAISS|Redis)\b', text
        )
        for t in tech:
            entities.append((t, "technology"))

        return entities[:20]   # cap per turn


# ── Unified Memory Retriever ──────────────────────────────────────

class UnifiedMemoryRetriever:
    """
    Combines results from:
      - V9 FAISS vector memory
      - EpisodicMemory
      - SemanticGraph
    into a single enriched context block.
    """

    def __init__(
        self,
        base_memory,    # V9 MemoryServiceV10
        episodic: EpisodicMemory,
        graph: SemanticGraph,
        emotional_tagging: bool = True,
    ) -> None:
        self._base     = base_memory
        self._episodic = episodic
        self._graph    = graph
        self._emotional = emotional_tagging

    async def retrieve(
        self,
        session_id: str,
        prompt: str,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Returns unified context dict with:
          - recent_turns: list[dict]
          - episodic:     list[Episode]
          - graph_context: list[dict]
          - emotion:      str
          - enriched_prompt: str (ready to inject into LLM)
        """
        emotion = detect_emotion(prompt) if self._emotional else "neutral"

        # Run retrievals in parallel
        recent_task  = asyncio.create_task(
            self._base.get_context(session_id=session_id, prompt=prompt)
        )
        episodic_task = asyncio.create_task(
            self._episodic.recall(session_id=session_id, limit=3)
        )
        recent, episodes = await asyncio.gather(recent_task, episodic_task)

        # Graph enrichment (synchronous — in-memory)
        graph_hits = self._graph.query(prompt, top_k=3)

        # Update graph
        self._graph.update(prompt)

        # Build enriched context
        enriched = self._build_enriched_context(
            prompt, recent, episodes, graph_hits, emotion
        )

        return {
            "recent_turns":    recent,
            "episodic":        episodes,
            "graph_context":   graph_hits,
            "emotion":         emotion,
            "enriched_prompt": enriched,
        }

    def _build_enriched_context(
        self,
        prompt: str,
        recent: List[dict],
        episodes: List[Episode],
        graph: List[dict],
        emotion: str,
    ) -> str:
        parts = []

        if graph:
            graph_str = ", ".join(g["entity"] for g in graph[:3])
            parts.append(f"[Known entities: {graph_str}]")

        if episodes:
            ep_str = f"[User's recent emotion: {episodes[0].emotion}]"
            parts.append(ep_str)

        if emotion != "neutral":
            parts.append(f"[Current emotional tone: {emotion}]")

        return "\n".join(parts)
