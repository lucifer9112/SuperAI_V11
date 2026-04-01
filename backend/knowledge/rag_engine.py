"""
SuperAI V11 — backend/knowledge/rag_engine.py

FEATURE 5: RAG++ (Real-Time Knowledge Integration)

Pipeline for every query:
  1. WebRetriever   — live DuckDuckGo search + optional RSS feeds
  2. Chunker        — split documents into overlapping chunks
  3. ChunkEmbedder  — embed chunks with sentence-transformers
  4. ChunkRetriever — FAISS search over embedded chunks
  5. ContextBuilder — inject top-k chunks into LLM prompt

Cache: results TTL-cached to avoid repeated searches.
Colab-friendly: all deps already in requirements/colab.txt.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class Chunk:
    text:       str
    source:     str
    chunk_id:   int
    score:      float = 0.0


class TextChunker:
    """Split text into overlapping chunks."""

    def __init__(self, chunk_size: int = 400, overlap: int = 80) -> None:
        self.chunk_size = chunk_size
        self.overlap    = overlap

    def chunk(self, text: str, source: str) -> List[Chunk]:
        words  = text.split()
        chunks = []
        step   = max(self.chunk_size - self.overlap, 50)
        i      = 0
        cid    = 0
        while i < len(words):
            chunk_words = words[i : i + self.chunk_size]
            chunks.append(Chunk(
                text=" ".join(chunk_words),
                source=source,
                chunk_id=cid,
            ))
            i += step
            cid += 1
        return chunks


class WebRetriever:
    """Retrieve web results for a query."""

    def __init__(self, max_results: int = 5) -> None:
        self.max_results = max_results

    async def retrieve(self, query: str) -> List[Dict[str, str]]:
        def _search():
            try:
                from duckduckgo_search import DDGS
                with DDGS() as d:
                    return list(d.text(query, max_results=self.max_results))
            except Exception as e:
                logger.warning("Web search failed", error=str(e))
                return []

        results = await asyncio.to_thread(_search)
        return [
            {"title": r.get("title",""), "body": r.get("body",""), "url": r.get("href","")}
            for r in results
        ]


class ChunkIndex:
    """
    In-memory FAISS index over document chunks.
    Created fresh per query (no persistence needed for RAG).
    """

    def __init__(self) -> None:
        self._embedder = None
        self._ready    = False

    def _ensure_embedder(self) -> bool:
        if self._embedder is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
            self._ready    = True
            return True
        except ImportError:
            return False

    def search(self, query: str, chunks: List[Chunk], top_k: int = 5) -> List[Chunk]:
        if not self._ensure_embedder() or not chunks:
            return chunks[:top_k]

        try:
            import faiss, numpy as np

            texts  = [c.text for c in chunks]
            embeds = self._embedder.encode(
                [query] + texts, normalize_embeddings=True
            ).astype("float32")
            q_emb    = embeds[:1]
            doc_embs = embeds[1:]

            dim   = doc_embs.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(doc_embs)
            D, I  = index.search(q_emb, min(top_k, len(chunks)))

            results = []
            for dist, idx in zip(D[0], I[0]):
                if idx >= 0:
                    c = chunks[idx]
                    c.score = float(dist)
                    results.append(c)
            return results
        except Exception as e:
            logger.warning("Chunk search failed, returning first chunks", error=str(e))
            return chunks[:top_k]


class RAGEngine:
    """
    Full RAG++ pipeline:
      query → web retrieve → chunk → embed → retrieve → inject context
    """

    def __init__(self, cfg, monitoring=None) -> None:
        self.cfg         = cfg
        self._enabled    = getattr(cfg, "enabled", False) if cfg is not None else False
        self._chunk_size = getattr(cfg, "chunk_size", 400)
        self._overlap    = getattr(cfg, "chunk_overlap", 80)
        self._top_k      = getattr(cfg, "top_k_chunks", 5)
        self._max_web    = getattr(cfg, "max_web_results", 5)
        self._cache_ttl  = getattr(cfg, "cache_ttl_s", 3600)

        self._chunker    = TextChunker(self._chunk_size, self._overlap)
        self._retriever  = WebRetriever(self._max_web)
        self._index      = ChunkIndex()
        self._monitoring = monitoring

        # TTL cache: query_hash → (timestamp, context_str)
        self._cache: Dict[str, Tuple[float, str]] = {}
        self._cache_lock = asyncio.Lock()
        self._inflight: Dict[str, asyncio.Future[str]] = {}

        logger.info("RAGEngine ready", enabled=self._enabled)

    async def retrieve_context(
        self,
        query: str,
        use_cache: bool = True,
    ) -> str:
        """
        Main entry point.
        Returns a formatted context string ready to inject into an LLM prompt.
        """
        if not self._enabled:
            return ""

        cache_key = hashlib.md5(query.encode()).hexdigest()
        waiter: Optional[asyncio.Future[str]] = None
        leader = False
        now = time.time()

        async with self._cache_lock:
            self._prune_cache(now)
            if use_cache and cache_key in self._cache:
                ts, ctx = self._cache[cache_key]
                if now - ts < self._cache_ttl:
                    logger.debug("RAG cache hit", query=query[:40])
                    if self._monitoring:
                        self._monitoring.record_cache_event("rag", "hit")
                    return ctx
                self._cache.pop(cache_key, None)

            if use_cache and cache_key in self._inflight:
                waiter = self._inflight[cache_key]
            else:
                waiter = asyncio.get_running_loop().create_future()
                self._inflight[cache_key] = waiter
                leader = True

        if not leader:
            if self._monitoring:
                self._monitoring.record_cache_event("rag", "wait")
            return await waiter

        try:
            # 1. Web search
            web_results = await self._retriever.retrieve(query)
            if not web_results:
                ctx = ""
            else:
                # 2. Chunk
                all_chunks: List[Chunk] = []
                for r in web_results:
                    text   = f"{r['title']}. {r['body']}"
                    source = r.get("url", r["title"])
                    all_chunks.extend(self._chunker.chunk(text, source))

                # 3. Rank chunks
                top_chunks = await asyncio.to_thread(
                    self._index.search, query, all_chunks, self._top_k
                )

                # 4. Format context
                ctx = self._format_context(top_chunks)

            async with self._cache_lock:
                if use_cache:
                    self._cache[cache_key] = (time.time(), ctx)
                    self._prune_cache()
                future = self._inflight.pop(cache_key, None)
                if future and not future.done():
                    future.set_result(ctx)

            if self._monitoring:
                self._monitoring.record_cache_event("rag", "miss")
            return ctx

        except asyncio.CancelledError:
            logger.warning("RAG pipeline cancelled", query=query[:40])
            await self._resolve_inflight(cache_key, "")
            if self._monitoring:
                self._monitoring.record_cache_event("rag", "cancelled")
            raise
        except Exception as e:
            logger.warning("RAG pipeline error", error=str(e))
            await self._resolve_inflight(cache_key, "")
            if self._monitoring:
                self._monitoring.record_cache_event("rag", "error")
                self._monitoring.record_error("rag")
            return ""

    def _format_context(self, chunks: List[Chunk]) -> str:
        if not chunks:
            return ""
        parts = ["[Retrieved Knowledge]"]
        for i, c in enumerate(chunks, 1):
            parts.append(f"[{i}] {c.text[:300]} (source: {c.source[:60]})")
        return "\n".join(parts)

    def clear_cache(self) -> None:
        self._cache.clear()
        if self._monitoring:
            self._monitoring.record_cache_event("rag", "clear")

    async def _resolve_inflight(self, cache_key: str, result: str) -> None:
        async with self._cache_lock:
            future = self._inflight.pop(cache_key, None)
            if future and not future.done():
                future.set_result(result)

    def _prune_cache(self, now: Optional[float] = None) -> None:
        now = now or time.time()
        expired = [
            key for key, (ts, _) in self._cache.items()
            if now - ts >= self._cache_ttl
        ]
        for key in expired:
            self._cache.pop(key, None)

        while len(self._cache) > 200:
            oldest = min(self._cache, key=lambda key: self._cache[key][0])
            self._cache.pop(oldest, None)
            if self._monitoring:
                self._monitoring.record_cache_event("rag", "evict")
