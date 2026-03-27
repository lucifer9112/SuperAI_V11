"""SuperAI V11 — backend/services/monitoring_service.py"""
from __future__ import annotations
import time
from collections import defaultdict
from typing import Dict, List
from loguru import logger


class MonitoringService:
    def __init__(self) -> None:
        self._requests: int             = 0
        self._errors:   int             = 0
        self._tokens:   int             = 0
        self._by_task:  Dict[str, int]  = defaultdict(int)
        self._by_model: Dict[str, int]  = defaultdict(int)
        self._latencies: List[float]    = []
        self._start     = time.time()
        self._prom_ok   = False
        try:
            from prometheus_client import Counter, Histogram
            self._req_ctr  = Counter("superai_v11_requests_total", "Requests", ["task", "model"])
            self._lat_hist = Histogram("superai_v11_latency_ms",   "Latency ms",
                                        buckets=[50,100,200,500,1000,2000,5000])
            self._tok_ctr  = Counter("superai_v11_tokens_total",   "Tokens")
            self._prom_ok  = True
        except ImportError:
            pass

    def record_request(
        self, task_type: str, model: str,
        latency_ms: float, tokens: int = 0, error: bool = False,
    ) -> None:
        self._requests += 1
        self._tokens   += tokens
        self._by_task[task_type]  += 1
        self._by_model[model]     += 1
        self._latencies.append(latency_ms)
        if error:
            self._errors += 1
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-1000:]
        if self._prom_ok:
            self._req_ctr.labels(task=task_type, model=model).inc()
            self._lat_hist.observe(latency_ms)
            self._tok_ctr.inc(tokens)

    def total_requests(self) -> int:
        return self._requests

    def avg_latency(self) -> float:
        return round(sum(self._latencies) / len(self._latencies), 2) if self._latencies else 0.0

    def loaded_models(self) -> List[str]:
        return list(self._by_model.keys())

    def summary(self) -> dict:
        return {
            "requests_total": self._requests,
            "errors_total":   self._errors,
            "tokens_total":   self._tokens,
            "avg_latency_ms": self.avg_latency(),
            "by_task":        dict(self._by_task),
            "by_model":       dict(self._by_model),
            "uptime_s":       round(time.time() - self._start, 1),
        }
