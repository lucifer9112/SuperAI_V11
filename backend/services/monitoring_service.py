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
        self._errors_by_kind: Dict[str, int] = defaultdict(int)
        self._tool_calls: Dict[str, int] = defaultdict(int)
        self._tool_failures: Dict[str, int] = defaultdict(int)
        self._security_events: Dict[str, int] = defaultdict(int)
        self._cache_events: Dict[str, int] = defaultdict(int)
        self._latencies: List[float]    = []
        self._start     = time.time()
        self._prom_ok   = False
        try:
            from prometheus_client import Counter, Histogram
            self._req_ctr  = Counter("superai_v11_requests_total", "Requests", ["task", "model"])
            self._lat_hist = Histogram("superai_v11_latency_ms",   "Latency ms",
                                        buckets=[50,100,200,500,1000,2000,5000])
            self._tok_ctr  = Counter("superai_v11_tokens_total",   "Tokens")
            self._err_ctr  = Counter("superai_v11_errors_total", "Errors", ["kind"])
            self._tool_ctr = Counter("superai_v11_tool_calls_total", "Tool calls", ["tool", "success"])
            self._sec_ctr  = Counter("superai_v11_security_events_total", "Security events", ["threat_type", "blocked"])
            self._cache_ctr = Counter("superai_v11_cache_events_total", "Cache events", ["cache", "outcome"])
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
            self.record_error("request")
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-1000:]
        if self._prom_ok:
            self._req_ctr.labels(task=task_type, model=model).inc()
            self._lat_hist.observe(latency_ms)
            self._tok_ctr.inc(tokens)

    def record_error(self, kind: str = "generic") -> None:
        self._errors += 1
        self._errors_by_kind[kind] += 1
        if self._prom_ok:
            self._err_ctr.labels(kind=kind).inc()

    def record_tool(self, tool_name: str, success: bool) -> None:
        self._tool_calls[tool_name] += 1
        if not success:
            self._tool_failures[tool_name] += 1
        if self._prom_ok:
            self._tool_ctr.labels(tool=tool_name, success=str(success).lower()).inc()

    def record_security_event(self, threat_type: str, blocked: bool) -> None:
        key = f"{threat_type}|blocked={str(blocked).lower()}"
        self._security_events[key] += 1
        if self._prom_ok:
            self._sec_ctr.labels(
                threat_type=threat_type or "unknown",
                blocked=str(blocked).lower(),
            ).inc()

    def record_cache_event(self, cache_name: str, outcome: str) -> None:
        key = f"{cache_name}:{outcome}"
        self._cache_events[key] += 1
        if self._prom_ok:
            self._cache_ctr.labels(cache=cache_name, outcome=outcome).inc()

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
            "errors_by_kind": dict(self._errors_by_kind),
            "tool_calls":     dict(self._tool_calls),
            "tool_failures":  dict(self._tool_failures),
            "security_events": dict(self._security_events),
            "cache_events":   dict(self._cache_events),
            "uptime_s":       round(time.time() - self._start, 1),
        }
