"""
SuperAI V11 — backend/agents/parallel_executor.py

FEATURE 4: Parallel Multi-Agent System

Architecture:
  ParallelAgentExecutor
    ├── ResearchAgent   — web search + synthesis
    ├── CodingAgent     — code generation/review
    ├── ReasoningAgent  — logical analysis + math
    └── PlanningAgent   — task decomposition + timeline

Execution modes:
  1. SINGLE   — best-fit agent handles the goal
  2. PARALLEL — multiple agents work simultaneously on sub-goals
  3. PIPELINE — agents work in sequence (plan → research → code → review)

Conflict resolution: confidence-weighted answer merging
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


# ── Agent result ──────────────────────────────────────────────────

@dataclass
class AgentResult:
    agent_type:  str
    answer:      str
    confidence:  float
    steps:       int
    latency_ms:  float
    error:       Optional[str] = None


# ── Specialized agent bases ───────────────────────────────────────

class SpecializedAgent:
    """Base class for all specialized agents."""

    agent_type: str = "base"
    system_prompt: str = "You are a helpful AI agent."

    def __init__(self, model_loader, tool_timeout: int = 30) -> None:
        self._models      = model_loader
        self._timeout     = tool_timeout

    async def run(self, goal: str, context: str = "", model_name: str = "") -> AgentResult:
        t0 = time.perf_counter()
        try:
            prompt = self._build_prompt(goal, context)
            answer, _ = await asyncio.wait_for(
                self._models.infer(
                    model_name=model_name or "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                    prompt=prompt,
                    max_tokens=512,
                    temperature=0.4,
                ),
                timeout=self._timeout,
            )
            confidence = self._score_answer(answer)
            return AgentResult(
                agent_type=self.agent_type, answer=answer,
                confidence=confidence, steps=1,
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        except asyncio.TimeoutError:
            return AgentResult(
                agent_type=self.agent_type, answer="",
                confidence=0.0, steps=0,
                latency_ms=(time.perf_counter() - t0) * 1000,
                error="timeout",
            )
        except Exception as e:
            return AgentResult(
                agent_type=self.agent_type, answer="",
                confidence=0.0, steps=0,
                latency_ms=(time.perf_counter() - t0) * 1000,
                error=str(e),
            )

    def _build_prompt(self, goal: str, context: str) -> str:
        ctx = f"\nContext:\n{context}\n" if context else ""
        return f"{self.system_prompt}{ctx}\n\nTask: {goal}\n\nResponse:"

    @staticmethod
    def _score_answer(answer: str) -> float:
        if not answer or len(answer.strip()) < 10:
            return 0.1
        words = len(answer.split())
        return min(0.4 + words / 200, 0.95)


class ResearchAgent(SpecializedAgent):
    agent_type    = "research"
    system_prompt = (
        "You are a research specialist. Your job is to find, analyse, "
        "and synthesise information. Provide factual, well-structured answers "
        "with key points highlighted. Use web search when available."
    )

    async def run(self, goal: str, context: str = "", model_name: str = "") -> AgentResult:
        # Try web search first
        search_context = await self._web_search(goal)
        combined_context = f"{context}\n\nSearch results:\n{search_context}" if search_context else context
        return await super().run(goal, combined_context, model_name)

    async def _web_search(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as d:
                results = list(d.text(query, max_results=3))
            return "\n".join(f"- {r['title']}: {r['body'][:200]}" for r in results)
        except Exception:
            return ""


class CodingAgent(SpecializedAgent):
    agent_type    = "coding"
    system_prompt = (
        "You are an expert software engineer. Write clean, efficient, "
        "well-commented code. Include error handling and tests where relevant. "
        "Follow best practices for the language being used."
    )


class ReasoningAgent(SpecializedAgent):
    agent_type    = "reasoning"
    system_prompt = (
        "You are a logical reasoning specialist. Break down complex problems "
        "step-by-step. Show your reasoning chain clearly. "
        "For math problems, show all calculation steps. "
        "State assumptions explicitly."
    )


class PlanningAgent(SpecializedAgent):
    agent_type    = "planning"
    system_prompt = (
        "You are a strategic planning specialist. Decompose complex goals "
        "into actionable steps with clear priorities and dependencies. "
        "Estimate timeframes and identify risks. "
        "Output a structured plan with phases."
    )


# ── Parallel Executor ─────────────────────────────────────────────

class ExecutionMode(str, Enum):
    SINGLE   = "single"
    PARALLEL = "parallel"
    PIPELINE = "pipeline"


@dataclass
class ParallelExecutionResult:
    mode:          str
    goal:          str
    final_answer:  str
    agent_results: List[AgentResult]
    winner_agent:  str
    confidence:    float
    latency_ms:    float
    run_id:        str = field(default_factory=lambda: str(uuid.uuid4())[:8])


class ParallelAgentExecutor:
    """
    Routes goals to specialized agents and executes them in parallel.
    Merges results using confidence-weighted selection.
    """

    def __init__(self, model_loader, cfg) -> None:
        self.cfg     = cfg
        timeout      = getattr(cfg, "tool_timeout", 30)
        self._agents = {
            "research":  ResearchAgent(model_loader,  timeout),
            "coding":    CodingAgent(model_loader,    timeout),
            "reasoning": ReasoningAgent(model_loader, timeout),
            "planning":  PlanningAgent(model_loader,  timeout),
        }
        self._max_concurrent = getattr(cfg, "max_concurrent_agents", 4)
        logger.info("ParallelAgentExecutor ready", agents=list(self._agents.keys()))

    async def execute(
        self,
        goal: str,
        mode: ExecutionMode = ExecutionMode.PARALLEL,
        selected_agents: Optional[List[str]] = None,
        context: str = "",
        model_name: str = "",
    ) -> ParallelExecutionResult:
        t0      = time.perf_counter()
        agents  = selected_agents or self._select_agents(goal)
        agents  = agents[:self._max_concurrent]

        if mode == ExecutionMode.SINGLE:
            results = [await self._agents[agents[0]].run(goal, context, model_name)]
        elif mode == ExecutionMode.PIPELINE:
            results = await self._run_pipeline(goal, agents, model_name)
        else:
            results = await self._run_parallel(goal, agents, context, model_name)

        final_answer, winner = self._merge_results(results)
        elapsed = (time.perf_counter() - t0) * 1000

        return ParallelExecutionResult(
            mode=mode.value, goal=goal,
            final_answer=final_answer,
            agent_results=results,
            winner_agent=winner,
            confidence=max((r.confidence for r in results), default=0.0),
            latency_ms=elapsed,
        )

    async def _run_parallel(
        self, goal: str, agents: List[str], context: str, model_name: str
    ) -> List[AgentResult]:
        tasks = [
            self._agents[a].run(goal, context, model_name)
            for a in agents if a in self._agents
        ]
        return await asyncio.gather(*tasks)

    async def _run_pipeline(
        self, goal: str, agents: List[str], model_name: str
    ) -> List[AgentResult]:
        results: List[AgentResult] = []
        accumulated_context = ""
        for agent_name in agents:
            if agent_name not in self._agents:
                continue
            result = await self._agents[agent_name].run(
                goal, accumulated_context, model_name
            )
            results.append(result)
            accumulated_context += f"\n[{agent_name.upper()} output]: {result.answer[:300]}"
        return results

    def _select_agents(self, goal: str) -> List[str]:
        """Auto-select relevant agents based on goal keywords."""
        goal_lower = goal.lower()
        selected   = []
        if any(kw in goal_lower for kw in ["search","find","research","latest","news"]):
            selected.append("research")
        if any(kw in goal_lower for kw in ["code","function","python","debug","implement"]):
            selected.append("coding")
        if any(kw in goal_lower for kw in ["reason","analyze","why","prove","calculate","math"]):
            selected.append("reasoning")
        if any(kw in goal_lower for kw in ["plan","steps","roadmap","strategy","schedule"]):
            selected.append("planning")
        return selected or ["research", "reasoning"]

    def _merge_results(self, results: List[AgentResult]) -> Tuple[str, str]:
        """Confidence-weighted result merging."""
        valid = [r for r in results if r.answer and not r.error]
        if not valid:
            return "No agent could complete the task.", "none"
        best = max(valid, key=lambda r: r.confidence)
        return best.answer, best.agent_type
