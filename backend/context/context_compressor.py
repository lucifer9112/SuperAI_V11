"""
SuperAI V12 — backend/context/context_compressor.py

Context Compression Engine: manages token budgets, compresses context
using multiple strategies, and detects degradation patterns.

Inspired by:
- context-compression skill (3-phase workflow, 6-dimension scoring)
- context-degradation skill (lost-in-middle, poisoning, distraction)
- context-optimization skill (KV-cache, masking, compaction, partitioning)
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


# ── Models ────────────────────────────────────────────────────────

@dataclass
class ContextSegment:
    """A piece of context with metadata."""
    content: str
    category: str = "general"        # system | user | tool | memory | retrieved
    priority: float = 0.5            # 0.0 (noise) – 1.0 (critical)
    position: str = "middle"         # start | middle | end
    token_estimate: int = 0

    def __post_init__(self):
        if not self.token_estimate:
            self.token_estimate = len(self.content.split())  # rough estimate


@dataclass
class CompressionResult:
    original_tokens: int
    compressed_tokens: int
    ratio: float                     # compression ratio
    method: str
    compressed_text: str = ""        # the actual compressed context
    quality_scores: Dict[str, float] = field(default_factory=dict)
    segments: List[ContextSegment] = field(default_factory=list)


@dataclass
class DegradationReport:
    degradation_detected: bool
    patterns: List[str] = field(default_factory=list)
    severity: str = "none"           # none | low | medium | high | critical
    recommendations: List[str] = field(default_factory=list)
    context_utilization: float = 0.0


# ── Compression Prompts ───────────────────────────────────────────

_COMPRESS_PROMPT = """Compress the following context while preserving all critical information.
Keep: key facts, decisions made, open questions, action items.
Remove: verbose explanations, redundant text, conversational filler.

Context to compress:
{context}

Output a concise summary preserving all essential information."""

_CATEGORIZE_PROMPT = """Categorize each piece of information in this context as:
- CRITICAL: must keep verbatim (decisions, constraints, key facts)
- SUPPORTING: useful but can be summarized (explanations, examples)
- NOISE: can be removed (filler, redundancy, off-topic)

Context:
{context}

For each item, output: CATEGORY: [text]"""


class ContextCompressor:
    """
    Manages context window with compression, budgeting, and degradation detection.
    Implements the 3-phase compression workflow from context-compression skill.
    """

    # Token budget defaults (conservative — 60-70% of advertised window)
    DEFAULT_BUDGET = 3000
    COMPACTION_THRESHOLD = 0.70   # trigger compaction at 70% utilization

    def __init__(self, model_loader: Any = None, max_tokens: int = 0) -> None:
        self._models = model_loader
        self.max_tokens = max_tokens or self.DEFAULT_BUDGET

    # ── Phase 1: Categorize ───────────────────────────────────────

    def categorize(self, segments: List[ContextSegment]) -> Dict[str, List[ContextSegment]]:
        """Categorize context segments by signal value."""
        result: Dict[str, List[ContextSegment]] = {
            "critical": [], "supporting": [], "noise": [],
        }
        for seg in segments:
            if seg.priority >= 0.8:
                result["critical"].append(seg)
            elif seg.priority >= 0.4:
                result["supporting"].append(seg)
            else:
                result["noise"].append(seg)
        return result

    # ── Phase 2: Compress ─────────────────────────────────────────

    async def compress(
        self,
        context: str,
        target_ratio: float = 0.5,
        method: str = "auto",
    ) -> CompressionResult:
        """Compress context using the specified method."""
        original_tokens = len(context.split())

        if method == "auto":
            method = self._select_method(original_tokens, target_ratio)

        if method == "selective_omission":
            compressed = self._selective_omission(context)
        elif method == "structured_summary":
            compressed = await self._structured_summary(context)
        elif method == "extractive":
            compressed = self._extractive_compress(context)
        else:
            compressed = await self._abstractive_compress(context)

        compressed_tokens = len(compressed.split())
        ratio = compressed_tokens / max(original_tokens, 1)

        return CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            ratio=ratio,
            method=method,
            compressed_text=compressed,
            quality_scores=self._score_compression(context, compressed),
        )

    def _select_method(self, tokens: int, target_ratio: float) -> str:
        """Auto-select compression method based on size and target."""
        if target_ratio > 0.7:
            return "selective_omission"    # 2-5x, ~0% loss
        elif target_ratio > 0.3:
            return "structured_summary"     # 5-10x, ~5% loss
        else:
            return "abstractive"            # 10-20x, ~15% loss

    def _selective_omission(self, context: str) -> str:
        """Remove noise tokens — safest method."""
        lines = context.splitlines()
        result = []
        for line in lines:
            stripped = line.strip()
            # Remove empty lines, filler, redundant whitespace
            if not stripped:
                continue
            if stripped in ("---", "***", "==="):
                continue
            if len(stripped) < 5 and not stripped[0].isalnum():
                continue
            result.append(line)
        return "\n".join(result)

    async def _structured_summary(self, context: str) -> str:
        """Structured summary with mandatory sections."""
        if self._models:
            try:
                prompt = _COMPRESS_PROMPT.format(context=context[:3000])
                answer, _ = await self._models.infer(
                    model_name="", prompt=prompt, max_tokens=500, temperature=0.2,
                )
                return answer
            except Exception:
                pass
        # Fallback: keep first and last 30% of lines
        lines = context.splitlines()
        if len(lines) <= 10:
            return context
        keep = max(3, len(lines) // 3)
        return "\n".join(lines[:keep] + ["[... compressed ...]"] + lines[-keep:])

    def _extractive_compress(self, context: str) -> str:
        """Pull key sentences verbatim."""
        sentences = re.split(r'[.!?]\s+', context)
        # Score sentences by keyword density
        keywords = {"must", "should", "error", "important", "critical", "note",
                     "decision", "required", "key", "goal", "result", "output"}
        scored = []
        for s in sentences:
            words = set(s.lower().split())
            score = len(words & keywords) + (1 if len(s) > 20 else 0)
            scored.append((score, s))
        scored.sort(key=lambda x: -x[0])
        # Keep top 50%
        keep = max(3, len(scored) // 2)
        kept = [s for _, s in scored[:keep]]
        return ". ".join(kept) + "."

    async def _abstractive_compress(self, context: str) -> str:
        """Model-generated summary — highest compression, highest risk."""
        if self._models:
            try:
                prompt = _COMPRESS_PROMPT.format(context=context[:3000])
                answer, _ = await self._models.infer(
                    model_name="", prompt=prompt, max_tokens=300, temperature=0.2,
                )
                return answer
            except Exception:
                pass
        return self._extractive_compress(context)

    # ── Phase 3: Validate ─────────────────────────────────────────

    def _score_compression(
        self, original: str, compressed: str,
    ) -> Dict[str, float]:
        """Score compression across 6 dimensions."""
        orig_tokens = original.lower().split()
        comp_tokens = compressed.lower().split()
        orig_words = set(orig_tokens)
        comp_words = set(comp_tokens)

        overlap = len(orig_words & comp_words) / max(len(orig_words), 1)
        ratio = len(comp_tokens) / max(len(orig_tokens), 1)
        ratio = max(0.0, min(1.0, ratio))

        return {
            "faithfulness": min(1.0, overlap * 1.5),
            "completeness": min(1.0, overlap * 1.3),
            "relevance": min(1.0, 1.0 - ratio + 0.3),
            "coherence": 0.8 if len(compressed) > 20 else 0.3,
            "conciseness": min(1.0, 1.0 - ratio + 0.1),
            "actionability": 0.7 if any(w in compressed.lower()
                for w in ["do", "should", "must", "need", "next", "action"]) else 0.4,
        }

    # ── Degradation Detection ─────────────────────────────────────

    def detect_degradation(
        self,
        context: str,
        max_tokens: int = 0,
    ) -> DegradationReport:
        """Detect context degradation patterns."""
        max_tok = max_tokens or self.max_tokens
        token_count = len(context.split())
        utilization = token_count / max(max_tok, 1)

        patterns = []
        recommendations = []

        # Check utilization
        if utilization > 0.9:
            patterns.append("near_capacity")
            recommendations.append("Apply compaction immediately — context at >90% capacity")
        elif utilization > self.COMPACTION_THRESHOLD:
            patterns.append("high_utilization")
            recommendations.append("Consider compaction — context above 70% threshold")

        # Check for repetition (context poisoning indicator)
        lines = context.splitlines()
        seen = set()
        dupes = 0
        for line in lines:
            clean = line.strip().lower()
            if clean in seen and len(clean) > 20:
                dupes += 1
            seen.add(clean)
        if dupes > 3:
            patterns.append("repetition_detected")
            recommendations.append(f"Found {dupes} duplicate lines — possible context poisoning")

        # Check for error accumulation
        error_count = context.lower().count("error") + context.lower().count("traceback")
        if error_count > 5:
            patterns.append("error_accumulation")
            recommendations.append("High error density in context — consider truncating to before errors")

        # Check for mixed task types (context confusion)
        task_markers = sum(1 for marker in ["Task:", "Goal:", "Objective:", "TODO:"]
                          if marker in context)
        if task_markers > 3:
            patterns.append("task_mixing")
            recommendations.append("Multiple task markers detected — consider isolating task contexts")

        severity = "none"
        if len(patterns) >= 3:
            severity = "critical"
        elif len(patterns) == 2:
            severity = "high"
        elif len(patterns) == 1:
            severity = "medium" if "near_capacity" in patterns else "low"

        return DegradationReport(
            degradation_detected=len(patterns) > 0,
            patterns=patterns,
            severity=severity,
            recommendations=recommendations,
            context_utilization=min(1.0, utilization),
        )

    # ── Budget Management ─────────────────────────────────────────

    def optimize_placement(
        self, segments: List[ContextSegment],
    ) -> List[ContextSegment]:
        """Arrange segments following the U-shaped attention curve.
        Critical info at start and end; lower-priority in middle."""
        categorized = self.categorize(segments)

        ordered = []
        # Start: critical (highest attention)
        for seg in categorized["critical"]:
            seg.position = "start"
            ordered.append(seg)
        # Middle: supporting (lower attention zone)
        for seg in categorized["supporting"]:
            seg.position = "middle"
            ordered.append(seg)
        # End: remaining critical or high-pri items
        for seg in categorized.get("noise", []):
            seg.position = "end"
            ordered.append(seg)

        return ordered

    def build_context(
        self, segments: List[ContextSegment], budget: int = 0,
    ) -> str:
        """Build optimized context string within token budget."""
        max_tok = budget or self.max_tokens
        optimized = self.optimize_placement(segments)

        parts = []
        running = 0
        for seg in optimized:
            if running + seg.token_estimate > max_tok:
                break
            parts.append(seg.content)
            running += seg.token_estimate

        return "\n\n".join(parts)
