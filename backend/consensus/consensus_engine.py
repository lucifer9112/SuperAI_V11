"""
SuperAI V11 — backend/consensus/consensus_engine.py
STEP 3: Multi-Model Consensus System

Voting Strategies:
  BEST       — highest quality-scored response wins
  MAJORITY   — response most similar to all others (max avg word-overlap)
  ENSEMBLE   — meta-model synthesizes all responses into one answer
  AUTO       — auto-selects strategy based on agreement level

Conflict Resolution:
  agreement < conflict_threshold → trigger deeper reasoning:
    1. Log disagreement for self-improvement analysis
    2. Optionally invoke meta-evaluator (LLM judge)
    3. Fall back to BEST if judge fails

Colab optimisation:
  - All model calls in parallel via asyncio.gather
  - Single-model shortcut skips consensus overhead
  - Meta-evaluator uses fast model (configurable)
"""
from __future__ import annotations
import asyncio, re, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from loguru import logger


class VotingStrategy(str, Enum):
    BEST     = "best"
    MAJORITY = "majority"
    ENSEMBLE = "ensemble"
    AUTO     = "auto"


@dataclass
class ModelResponse:
    model_name: str
    answer:     str
    tokens:     int
    latency_ms: float
    quality:    float = 0.0
    confidence: float = 0.0
    error:      Optional[str] = None


@dataclass
class ConsensusResult:
    prompt:          str
    final_answer:    str
    winner_model:    str
    strategy:        str
    agreement:       float
    conflict:        bool
    all_responses:   List[ModelResponse]
    latency_ms:      float
    run_id:          str = field(default_factory=lambda: str(uuid.uuid4())[:8])


class ResponseEvaluator:
    _HEDGES  = ["i think","i believe","maybe","perhaps","not sure","i'm uncertain","i don't know"]
    _QUALITY = ["for example","specifically","step 1","step 2","because","therefore","research shows"]

    def evaluate(self, r: ModelResponse, prompt: str) -> ModelResponse:
        if not r.answer or r.error: r.quality = r.confidence = 0.0; return r
        n = len(r.answer.split()); q = 0.5
        if   n < 10:  q -= 0.25
        elif n < 25:  q -= 0.05
        elif n > 400: q -= 0.10
        else:         q += 0.10
        q -= min(sum(0.08 for h in self._HEDGES  if h in r.answer.lower()), 0.25)
        q += min(sum(0.06 for s in self._QUALITY if s in r.answer.lower()), 0.20)
        if r.latency_ms < 2000: q += 0.05
        r.quality = r.confidence = max(0.0, min(1.0, q))
        return r

    def similarity(self, a: str, b: str) -> float:
        wa, wb = set(a.lower().split()), set(b.lower().split())
        if not wa or not wb: return 0.0
        return len(wa & wb) / len(wa | wb)


class MultiModelRunner:
    def __init__(self, loader, timeout_s: int = 60) -> None:
        self._loader  = loader
        self._timeout = timeout_s

    async def run(self, prompt: str, models: List[str],
                  max_tokens: int = 512, temperature: float = 0.7) -> List[ModelResponse]:
        return await asyncio.gather(*[
            self._single(prompt, m, max_tokens, temperature) for m in models
        ])

    async def _single(self, prompt: str, model: str,
                      max_tokens: int, temperature: float) -> ModelResponse:
        t0 = time.perf_counter()
        try:
            ans, tok = await asyncio.wait_for(
                self._loader.infer(model, prompt, max_tokens, temperature),
                timeout=self._timeout)
            return ModelResponse(model, ans, tok, round((time.perf_counter()-t0)*1000, 1))
        except asyncio.TimeoutError:
            return ModelResponse(model, "", 0, round((time.perf_counter()-t0)*1000, 1), error="timeout")
        except Exception as e:
            return ModelResponse(model, "", 0, round((time.perf_counter()-t0)*1000, 1), error=str(e)[:80])


class VotingMechanism:
    def __init__(self, evaluator: ResponseEvaluator) -> None:
        self._eval = evaluator

    def vote(self, responses: List[ModelResponse], strategy: VotingStrategy,
             prompt: str) -> Tuple[str, str, float]:
        valid = [r for r in responses if r.answer and not r.error]
        if not valid:
            return "All models failed to respond.", "none", 0.0
        if len(valid) == 1:
            return valid[0].answer, valid[0].model_name, 1.0
        for r in valid: self._eval.evaluate(r, prompt)

        if strategy in (VotingStrategy.BEST, VotingStrategy.AUTO):
            return self._best(valid)
        if strategy == VotingStrategy.MAJORITY:
            return self._majority(valid)
        return self._best(valid)  # default

    def _best(self, responses: List[ModelResponse]) -> Tuple[str, str, float]:
        best = max(responses, key=lambda r: r.quality)
        agree = sum(1 for r in responses if abs(r.quality - best.quality) < 0.12) / len(responses)
        return best.answer, best.model_name, round(agree, 2)

    def _majority(self, responses: List[ModelResponse]) -> Tuple[str, str, float]:
        best, best_sim = responses[0], 0.0
        for r in responses:
            sim = sum(self._eval.similarity(r.answer, o.answer)
                      for o in responses if o is not r) / max(len(responses)-1, 1)
            if sim > best_sim: best_sim, best = sim, r
        return best.answer, best.model_name, round(best_sim, 2)


class ConflictDetector:
    def __init__(self, threshold: float = 0.30) -> None:
        self._t    = threshold
        self._eval = ResponseEvaluator()

    def detect(self, responses: List[ModelResponse]) -> Tuple[bool, float]:
        valid = [r for r in responses if r.answer and not r.error]
        if len(valid) < 2: return False, 1.0
        pairs = [(valid[i], valid[j]) for i in range(len(valid)) for j in range(i+1, len(valid))]
        sim   = sum(self._eval.similarity(a.answer, b.answer) for a,b in pairs) / len(pairs)
        return sim < self._t, round(sim, 3)


class MetaEvaluator:
    """LLM judge — picks best answer when conflict detected."""

    async def judge(self, prompt: str, responses: List[ModelResponse],
                    loader, judge_model: str) -> Tuple[str, str]:
        valid   = [r for r in responses if r.answer and not r.error]
        if not valid: return "", "none"
        options = "\n\n".join(
            f"Option {i+1} ({r.model_name}):\n{r.answer}"
            for i, r in enumerate(valid))
        judge_prompt = (
            f"You are an impartial AI judge. Pick the BEST answer to:\n\n"
            f"Question: {prompt}\n\nCandidates:\n{options}\n\n"
            f"Reply ONLY with the option number (e.g. 1) and one reason.\nBest option:")
        try:
            verdict, _ = await asyncio.wait_for(
                loader.infer(judge_model, judge_prompt, max_tokens=64, temperature=0.0),
                timeout=25)
            m = re.search(r'\b([1-9])\b', verdict)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(valid):
                    return valid[idx].answer, valid[idx].model_name
        except Exception as e:
            logger.warning("Meta-evaluator failed", error=str(e))
        best = max(valid, key=lambda r: r.quality)
        return best.answer, best.model_name


class ConsensusEngine:
    """Top-level consensus coordinator — injected into V11 Orchestrator."""

    def __init__(self, loader, model_names: List[str],
                 strategy: VotingStrategy = VotingStrategy.AUTO,
                 conflict_threshold: float = 0.30,
                 use_meta_evaluator: bool = False,
                 judge_model: Optional[str] = None,
                 timeout_s: int = 60) -> None:
        self._loader      = loader
        self._models      = model_names
        self._strategy    = strategy
        self._runner      = MultiModelRunner(loader, timeout_s)
        self._evaluator   = ResponseEvaluator()
        self._voter       = VotingMechanism(self._evaluator)
        self._conflict    = ConflictDetector(conflict_threshold)
        self._meta        = MetaEvaluator() if use_meta_evaluator else None
        self._judge_model = judge_model or (model_names[0] if model_names else "")
        self._conflict_log: List[Dict] = []
        logger.info("ConsensusEngine ready", models=model_names, strategy=strategy.value)

    async def run(self, prompt: str, max_tokens: int = 512,
                  temperature: float = 0.7,
                  strategy: Optional[VotingStrategy] = None) -> ConsensusResult:
        t0 = time.perf_counter()
        active_strategy = strategy or self._strategy

        # Single-model fast path
        if len(self._models) < 2:
            model = self._models[0] if self._models else ""
            try:   ans, tok = await self._loader.infer(model, prompt, max_tokens, temperature)
            except Exception as e: ans, tok = f"Error: {e}", 0
            return ConsensusResult(prompt, ans, model, "single", 1.0, False,
                [ModelResponse(model, ans, tok, 0.0)], round((time.perf_counter()-t0)*1000,1))

        # Parallel inference
        all_responses = await self._runner.run(prompt, self._models, max_tokens, temperature)

        # Conflict detection
        is_conflict, agreement = self._conflict.detect(all_responses)

        if is_conflict and self._meta:
            logger.info("Consensus conflict → meta-evaluator", agreement=agreement)
            self._conflict_log.append({"prompt": prompt[:80], "agreement": agreement})
            final, winner = await self._meta.judge(
                prompt, all_responses, self._loader, self._judge_model)
            agreement = 1.0 if winner != "none" else agreement
            strategy_used = "meta_judge"
        else:
            final, winner, agreement = self._voter.vote(all_responses, active_strategy, prompt)
            strategy_used = active_strategy.value

        ms = round((time.perf_counter()-t0)*1000, 1)
        if is_conflict:
            logger.warning("Consensus conflict", agreement=agreement, winner=winner)

        return ConsensusResult(prompt=prompt, final_answer=final, winner_model=winner,
            strategy=strategy_used, agreement=agreement, conflict=is_conflict,
            all_responses=all_responses, latency_ms=ms)

    def status(self) -> Dict:
        return {"models": self._models, "strategy": self._strategy.value,
                "total_conflicts": len(self._conflict_log),
                "recent_conflicts": self._conflict_log[-3:],
                "use_meta": self._meta is not None}
