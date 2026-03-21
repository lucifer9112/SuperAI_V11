"""
SuperAI V11 — backend/intelligence/model_registry.py

FEATURE 7: Custom Model Integration Layer

Capabilities:
  - Register models from HuggingFace Hub, local paths, LoRA adapters
  - Benchmark models on standard prompts
  - Auto-select best model per task based on benchmark scores
  - Hot-swap models without server restart
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class ModelEntry:
    model_id:    str            # HuggingFace ID or local path
    source:      str            # "huggingface" | "local" | "lora_adapter"
    tasks:       List[str]      # which tasks it handles
    description: str            = ""
    base_model:  Optional[str]  = None   # for LoRA adapters
    benchmark_scores: Dict[str, float] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    active:      bool = True


class ModelRegistry:
    """
    Central registry for all models used by SuperAI V11.
    Supports runtime registration, benchmarking, and auto-selection.
    """

    def __init__(self, cfg, model_loader) -> None:
        self.cfg          = cfg
        self._models_ref  = model_loader
        self._enabled     = getattr(cfg, "enabled", True)
        self._registry_path = Path(getattr(cfg, "registry_path", "data/model_registry.json"))
        self._benchmark_on_load = getattr(cfg, "benchmark_on_load", False)
        self._entries: Dict[str, ModelEntry] = {}
        self._load_registry()
        logger.info("ModelRegistry ready", entries=len(self._entries))

    # ── Registration ───────────────────────────────────────────────

    def register(
        self,
        model_id: str,
        source: str = "huggingface",
        tasks: Optional[List[str]] = None,
        description: str = "",
        base_model: Optional[str] = None,
    ) -> ModelEntry:
        entry = ModelEntry(
            model_id=model_id,
            source=source,
            tasks=tasks or ["chat"],
            description=description,
            base_model=base_model,
        )
        self._entries[model_id] = entry
        self._save_registry()
        logger.info("Model registered", model=model_id, source=source, tasks=tasks)
        return entry

    def deregister(self, model_id: str) -> bool:
        if model_id in self._entries:
            self._entries[model_id].active = False
            self._save_registry()
            return True
        return False

    def list_models(self, task: Optional[str] = None) -> List[ModelEntry]:
        entries = [e for e in self._entries.values() if e.active]
        if task:
            entries = [e for e in entries if task in e.tasks]
        return sorted(entries, key=lambda e: e.registered_at, reverse=True)

    # ── Benchmarking ───────────────────────────────────────────────

    async def benchmark(
        self,
        model_id: str,
        prompts: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        Run model on standard prompts, measure quality and speed.
        Returns dict of metric → score.
        """
        test_prompts = prompts or [
            "What is 2+2?",
            "Write a Python hello world function.",
            "Explain quantum entanglement in one sentence.",
        ]

        scores: Dict[str, float] = {}
        total_latency = 0.0
        success_count = 0

        for prompt in test_prompts:
            try:
                t0 = time.perf_counter()
                answer, tokens = await asyncio.wait_for(
                    self._models_ref.infer(model_id, prompt, max_tokens=128, temperature=0.1),
                    timeout=60,
                )
                latency = (time.perf_counter() - t0) * 1000
                total_latency += latency

                # Simple quality score: length + no error words
                quality = min(len(answer.split()) / 30.0, 1.0)
                if any(kw in answer.lower() for kw in ["error", "cannot", "unable"]):
                    quality *= 0.5

                success_count += 1
                scores[prompt[:30]] = round(quality, 3)

            except Exception as e:
                scores[prompt[:30]] = 0.0

        avg_quality = sum(scores.values()) / len(scores) if scores else 0.0
        avg_latency = total_latency / max(success_count, 1)

        result = {
            "avg_quality":   round(avg_quality, 3),
            "avg_latency_ms": round(avg_latency, 1),
            "success_rate":  round(success_count / len(test_prompts), 2),
            "overall_score": round(avg_quality * (1.0 - min(avg_latency / 10000, 0.5)), 3),
        }

        if model_id in self._entries:
            self._entries[model_id].benchmark_scores = result
            self._save_registry()

        logger.info("Benchmark complete", model=model_id, **result)
        return result

    # ── Auto-selection ─────────────────────────────────────────────

    def best_for_task(self, task: str) -> Optional[str]:
        """Return model_id with highest benchmark score for task."""
        candidates = self.list_models(task=task)
        if not candidates:
            return None
        scored = [
            (e, e.benchmark_scores.get("overall_score", 0.5))
            for e in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0].model_id if scored else None

    def get_entry(self, model_id: str) -> Optional[ModelEntry]:
        return self._entries.get(model_id)

    def summary(self) -> Dict:
        return {
            "total_registered": len(self._entries),
            "active":           sum(1 for e in self._entries.values() if e.active),
            "by_source":        self._count_by("source"),
            "by_task":          self._count_tasks(),
        }

    # ── Persistence ────────────────────────────────────────────────

    def _save_registry(self) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                mid: {
                    "model_id":  e.model_id,
                    "source":    e.source,
                    "tasks":     e.tasks,
                    "description": e.description,
                    "base_model": e.base_model,
                    "benchmark_scores": e.benchmark_scores,
                    "registered_at": e.registered_at,
                    "active":    e.active,
                }
                for mid, e in self._entries.items()
            }
            self._registry_path.write_text(json.dumps(data, indent=2))
        except Exception as ex:
            logger.warning("Registry save failed", error=str(ex))

    def _load_registry(self) -> None:
        if not self._registry_path.exists():
            return
        try:
            data = json.loads(self._registry_path.read_text())
            for mid, d in data.items():
                self._entries[mid] = ModelEntry(
                    model_id=d["model_id"], source=d["source"],
                    tasks=d["tasks"], description=d.get("description",""),
                    base_model=d.get("base_model"),
                    benchmark_scores=d.get("benchmark_scores",{}),
                    registered_at=d.get("registered_at", time.time()),
                    active=d.get("active", True),
                )
        except Exception as ex:
            logger.warning("Registry load failed", error=str(ex))

    def _count_by(self, attr: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self._entries.values():
            v = getattr(e, attr, "unknown")
            counts[v] = counts.get(v, 0) + 1
        return counts

    def _count_tasks(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self._entries.values():
            for t in e.tasks:
                counts[t] = counts.get(t, 0) + 1
        return counts
