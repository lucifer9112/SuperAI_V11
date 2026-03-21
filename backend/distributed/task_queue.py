"""
SuperAI V11 — backend/distributed/task_queue.py

FEATURE 10: Distributed & Scalable Architecture

Colab-compatible async task queue.
On Colab: uses asyncio (no Celery/Redis needed).
Production: swap backend to Celery or Ray with one config change.

Architecture:
  TaskQueue
    ├── AsyncBackend   — asyncio.Queue (Colab / single machine)
    ├── CeleryBackend  — Celery + Redis (production)
    └── RayBackend     — Ray (multi-GPU / cluster)

Workers use asyncio.Semaphore to limit concurrent model inference
(avoids OOM on Colab T4 with 15GB VRAM).
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from loguru import logger


class TaskStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    task_id:    str
    name:       str
    status:     TaskStatus = TaskStatus.PENDING
    result:     Any        = None
    error:      Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    ended_at:   Optional[float] = None
    priority:   int  = 5        # 1 (high) – 10 (low)

    @property
    def latency_ms(self) -> Optional[float]:
        if self.started_at and self.ended_at:
            return round((self.ended_at - self.started_at) * 1000, 2)
        return None


class AsyncTaskQueue:
    """
    Async task queue backed by asyncio.Queue.
    Supports task priorities (low number = higher priority).
    Limits concurrency to avoid OOM on Colab.
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._queue:   asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._tasks:   Dict[str, Task]       = {}
        self._sem      = asyncio.Semaphore(max_workers)
        self._workers: List[asyncio.Task]    = []
        self._running  = False
        self._max_workers = max_workers
        logger.info("AsyncTaskQueue ready", max_workers=max_workers)

    async def start(self) -> None:
        self._running = True
        for _ in range(self._max_workers):
            w = asyncio.create_task(self._worker())
            self._workers.append(w)

    async def stop(self) -> None:
        self._running = False
        for w in self._workers:
            w.cancel()

    async def submit(
        self,
        coro_fn: Callable[..., Coroutine],
        *args,
        name: str = "",
        priority: int = 5,
        **kwargs,
    ) -> str:
        """Submit a coroutine for execution. Returns task_id."""
        task_id = str(uuid.uuid4())[:10]
        task    = Task(task_id=task_id, name=name or coro_fn.__name__, priority=priority)
        self._tasks[task_id] = task

        # PriorityQueue: (priority, task_id, fn, args, kwargs)
        await self._queue.put((priority, task_id, coro_fn, args, kwargs))
        logger.debug("Task submitted", task_id=task_id, name=task.name)
        return task_id

    async def wait(self, task_id: str, timeout: float = 120.0) -> Optional[Any]:
        """Wait for task completion. Returns result or raises on failure."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            task = self._tasks.get(task_id)
            if task and task.status in (TaskStatus.DONE, TaskStatus.FAILED):
                if task.status == TaskStatus.FAILED:
                    raise RuntimeError(f"Task {task_id} failed: {task.error}")
                return task.result
            await asyncio.sleep(0.1)
        raise asyncio.TimeoutError(f"Task {task_id} timed out after {timeout}s")

    def status(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def queue_depth(self) -> int:
        return self._queue.qsize()

    def stats(self) -> Dict:
        done   = sum(1 for t in self._tasks.values() if t.status == TaskStatus.DONE)
        failed = sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)
        run    = sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)
        latencies = [t.latency_ms for t in self._tasks.values() if t.latency_ms]
        return {
            "total":       len(self._tasks),
            "pending":     self.queue_depth(),
            "running":     run,
            "done":        done,
            "failed":      failed,
            "max_workers": self._max_workers,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        }

    async def _worker(self) -> None:
        while self._running:
            try:
                priority, task_id, fn, args, kwargs = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                task = self._tasks.get(task_id)
                if not task:
                    continue

                async with self._sem:
                    task.status     = TaskStatus.RUNNING
                    task.started_at = time.time()
                    try:
                        task.result  = await fn(*args, **kwargs)
                        task.status  = TaskStatus.DONE
                    except Exception as e:
                        task.error  = str(e)
                        task.status = TaskStatus.FAILED
                        logger.error("Task failed", task_id=task_id, error=str(e))
                    finally:
                        task.ended_at = time.time()

                self._queue.task_done()
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break


# ── GPU-aware load balancer ───────────────────────────────────────

class GPULoadBalancer:
    """
    Simple round-robin GPU assignment for multi-GPU setups.
    On Colab (single T4): always returns GPU 0.
    """

    def __init__(self, gpu_ids: List[int]) -> None:
        self._gpus = gpu_ids or [0]
        self._idx  = 0

    def next_gpu(self) -> int:
        gpu = self._gpus[self._idx % len(self._gpus)]
        self._idx += 1
        return gpu

    def device_string(self) -> str:
        return f"cuda:{self.next_gpu()}"


# ── Task queue factory ────────────────────────────────────────────

def create_task_queue(cfg) -> AsyncTaskQueue:
    """
    Factory function — returns the right backend based on config.
    Currently: always returns AsyncTaskQueue (Colab compatible).
    Future: check cfg.task_queue for "celery" or "ray".
    """
    max_workers = getattr(cfg, "max_workers", 4)
    return AsyncTaskQueue(max_workers=max_workers)
