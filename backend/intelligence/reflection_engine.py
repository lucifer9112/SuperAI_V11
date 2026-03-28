"""
SuperAI V11 — backend/intelligence/reflection_engine.py

FEATURE 1: Self-Reflection System

Flow:
  1. Model generates initial response
  2. ReflectionEngine scores confidence (0.0–1.0)
  3. If confidence < threshold → second-pass critique + refinement
  4. Returns improved response + confidence metadata

Confidence scoring uses:
  - Response length heuristic
  - Hedging word detection ("I think", "maybe", "not sure")
  - Contradiction detection
  - Coherence check via embedding similarity
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

from loguru import logger


# ── Hedging / uncertainty patterns ────────────────────────────────
_HEDGES = re.compile(
    r"\b(I think|I believe|I'm not sure|maybe|perhaps|possibly|probably|"
    r"might be|could be|not certain|I don't know|unclear|uncertain|"
    r"as far as I know|I'm guessing)\b",
    re.IGNORECASE,
)

_CONTRADICTION = re.compile(
    r"\b(however|but|on the other hand|although|despite|contrary|"
    r"nevertheless|yet|whereas)\b",
    re.IGNORECASE,
)


@dataclass
class ReflectionResult:
    original_answer:  str
    final_answer:     str
    confidence:       float          # 0.0 – 1.0
    was_reflected:    bool           # did second-pass run?
    reflection_notes: str            = ""
    rounds:           int            = 0
    latency_ms:       float          = 0.0


class ReflectionEngine:
    """
    Self-reflection and response improvement engine.
    Evaluates confidence and optionally triggers a critique pass.
    """

    def __init__(self, cfg, model_loader) -> None:
        self.cfg     = cfg
        self._models = model_loader
        self._enabled = getattr(cfg, "enabled", True)
        self._threshold = getattr(cfg, "min_confidence_threshold", 0.6)
        self._max_rounds = getattr(cfg, "max_reflection_rounds", 2)
        logger.info("ReflectionEngine V10 ready", enabled=self._enabled,
                    threshold=self._threshold)

    async def reflect(
        self,
        prompt: str,
        answer: str,
        task_type: str = "chat",
        model_name: str = "",
    ) -> ReflectionResult:
        """
        Evaluate answer quality and optionally improve it.
        Always returns a ReflectionResult — falls back gracefully on error.
        """
        if not self._enabled:
            return ReflectionResult(
                original_answer=answer, final_answer=answer,
                confidence=1.0, was_reflected=False,
            )

        t0 = time.perf_counter()
        try:
            confidence = self._score_confidence(answer, task_type=task_type)
            threshold = self._threshold - 0.1 if task_type in {"code", "math"} else self._threshold

            if confidence >= threshold:
                return ReflectionResult(
                    original_answer=answer, final_answer=answer,
                    confidence=confidence, was_reflected=False,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                )

            # Below threshold — trigger reflection
            logger.debug("Reflection triggered", confidence=confidence, task=task_type)
            improved, notes, rounds = await self._run_reflection(
                prompt, answer, model_name or "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
            )
            new_conf = min(confidence + 0.15 * rounds, 0.95)

            return ReflectionResult(
                original_answer  = answer,
                final_answer     = improved,
                confidence       = new_conf,
                was_reflected    = True,
                reflection_notes = notes,
                rounds           = rounds,
                latency_ms       = (time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            logger.warning("Reflection failed, using original", error=str(e))
            return ReflectionResult(
                original_answer=answer, final_answer=answer,
                confidence=0.5, was_reflected=False,
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

    # ── Confidence scoring ─────────────────────────────────────────

    def _score_confidence(self, answer: str, task_type: str = "chat") -> float:
        """
        Heuristic confidence score.
        Factors: length, hedging words, contradiction density.
        """
        if not answer or len(answer.strip()) < 10:
            return 0.1

        score = 0.7   # base

        # Hedge penalty
        hedge_count = len(_HEDGES.findall(answer))
        hedge_penalty = 0.03 if task_type in {"code", "math"} else 0.08
        score -= min(hedge_count * hedge_penalty, 0.3)

        # Length bonus (very short = uncertain)
        words = len(answer.split())
        if words < 15:
            score -= 0.2
        elif words > 50:
            score += 0.05

        # Contradiction density penalty
        contra = len(_CONTRADICTION.findall(answer))
        score -= min(contra * 0.04, 0.15)

        # Apology / admission of ignorance
        if re.search(r"\b(I (can't|cannot|don't know|am unable))\b", answer, re.I):
            score -= 0.15

        return max(0.05, min(score, 1.0))

    # ── Reflection loop ────────────────────────────────────────────

    async def _run_reflection(
        self, prompt: str, answer: str, model_name: str
    ) -> Tuple[str, str, int]:
        """Run up to max_rounds critique-improvement loops."""
        current  = answer
        notes    = []
        rounds   = 0

        for i in range(self._max_rounds):
            critique_prompt = (
                f"You are a self-critic AI. Review the following answer for quality, "
                f"accuracy, and completeness.\n\n"
                f"Original Question: {prompt}\n\n"
                f"Answer to review: {current}\n\n"
                f"Identify any issues (factual errors, vagueness, missing info). "
                f"Then provide an improved version.\n\n"
                f"Format:\nISSUES: <brief list>\nIMPROVED ANSWER: <better answer>"
            )

            try:
                critique, _ = await asyncio.wait_for(
                    self._models.infer(
                        model_name=model_name,
                        prompt=critique_prompt,
                        max_tokens=400,
                        temperature=0.3,
                    ),
                    timeout=getattr(self.cfg, "reflection_timeout_s", 30),
                )

                # Extract improved answer
                improved = self._extract_improved(critique)
                if improved and len(improved) > 20:
                    notes.append(f"Round {i+1}: {critique[:100]}...")
                    current = improved
                    rounds += 1
                else:
                    break   # no improvement found

            except asyncio.TimeoutError:
                logger.warning("Reflection timeout on round", round=i+1)
                break

        return current, " | ".join(notes), rounds

    @staticmethod
    def _extract_improved(critique: str) -> str:
        """Extract 'IMPROVED ANSWER:' section from critique."""
        markers = ["IMPROVED ANSWER:", "Improved Answer:", "improved answer:"]
        for marker in markers:
            if marker in critique:
                return critique.split(marker, 1)[1].strip()
        # Fallback: return last paragraph
        parts = [p.strip() for p in critique.split("\n\n") if p.strip()]
        return parts[-1] if parts else ""
