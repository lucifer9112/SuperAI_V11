"""
SuperAI V11 — backend/tools/tool_calling_engine.py
STEP 2: Tool Calling Engine — Main Coordinator

Flow:
  1. prompt → ToolSelector.select() → [tool_names]
  2. For each tool: extract arguments from prompt
  3. Execute all tools in parallel via asyncio.gather
  4. Inject results into enriched prompt
  5. LLM generates grounded final answer
"""
from __future__ import annotations
import asyncio, re, time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from loguru import logger
from backend.tools.tool_registry import ToolRegistry, ToolResult, ToolSelector
from backend.tools.tool_executor import ToolExecutor


@dataclass
class ToolCall:
    tool_name:  str
    arguments:  Dict[str, Any]


@dataclass
class ToolCallingResult:
    prompt:          str
    tool_calls:      List[ToolCall]
    tool_results:    List[ToolResult]
    enriched_prompt: str
    tools_used:      List[str]
    total_ms:        float


class ToolArgExtractor:
    """Heuristic argument extraction — no LLM call needed."""

    def extract(self, tool_name: str, prompt: str) -> Dict[str, Any]:
        p = prompt
        if tool_name == "web_search":
            q = re.sub(r'\b(search|find|look up|what is|who is)\b', '', p, flags=re.I).strip()
            return {"query": q or p}
        if tool_name == "calculator":
            m = re.search(r'[\d\s\+\-\*\/\.\(\)\%\^]+', p)
            return {"expression": m.group(0).strip() if m else p}
        if tool_name == "code_execute":
            m = re.search(r'```(?:python)?\n?(.*?)```', p, re.DOTALL)
            return {"code": m.group(1).strip() if m else p}
        if tool_name == "wikipedia":
            c = re.sub(r'\b(who is|what is|tell me about|explain|describe)\b','',p,flags=re.I).strip()
            return {"topic": c or p}
        if tool_name == "weather":
            m = re.search(r'(?:weather|forecast|temperature)\s+(?:in\s+)?([A-Za-z\s,]+)', p, re.I)
            return {"city": m.group(1).strip() if m else p}
        if tool_name == "file_read":
            m = re.search(r'[\w\-\.]+\.\w{2,5}', p)
            return {"filename": m.group(0) if m else ""}
        return {}  # datetime and others need no args


class ToolCallingEngine:
    """
    Main tool-calling orchestrator.
    Injected into V11 Orchestrator as optional service.
    """

    def __init__(self, registry: ToolRegistry, model_loader=None,
                 model_name: str = "", use_llm_select: bool = False, monitoring=None) -> None:
        self._reg        = registry
        self._executor   = ToolExecutor(registry, monitoring=monitoring)
        self._selector   = ToolSelector(registry)
        self._extractor  = ToolArgExtractor()
        self._loader     = model_loader
        self._model_name = model_name
        self._use_llm    = use_llm_select and model_loader is not None
        logger.info("ToolCallingEngine ready", tools=len(registry), llm=self._use_llm)

    async def process(self, prompt: str, autonomy_level: int = 2,
                      max_tools: int = 3) -> ToolCallingResult:
        t0 = time.perf_counter()

        # Select tools
        if self._use_llm and self._loader:
            names = await self._selector.select_llm(prompt, self._loader, self._model_name, max_tools)
        else:
            names = self._selector.select(prompt, max_tools)

        if not names:
            return ToolCallingResult(prompt, [], [], prompt, [], 0.0)

        # Block unsafe tools at low autonomy
        safe_names = [n for n in names
                      if self._reg.get(n) and
                      (self._reg.get(n).safe or autonomy_level >= 3)]

        if not safe_names:
            return ToolCallingResult(prompt, [], [], prompt, [], 0.0)

        # Build tool calls
        calls = [ToolCall(n, self._extractor.extract(n, prompt)) for n in safe_names]

        # Execute in parallel
        results = await asyncio.gather(*[
            self._executor.execute(c.tool_name, c.arguments) for c in calls
        ])

        enriched = self._build_prompt(prompt, list(results))
        ms = (time.perf_counter()-t0)*1000

        logger.info("Tools executed", tools=safe_names, ms=round(ms,1))
        return ToolCallingResult(
            prompt=prompt, tool_calls=calls, tool_results=list(results),
            enriched_prompt=enriched,
            tools_used=[r.tool_name for r in results if r.success],
            total_ms=round(ms,1),
        )

    def _build_prompt(self, prompt: str, results: List[ToolResult]) -> str:
        successful = [r for r in results if r.success]
        if not successful: return prompt
        parts = [f"User question: {prompt}", "", "=== Tool Results ==="]
        parts += [r.to_context() for r in successful]
        parts += ["=== End Tool Results ===", "",
                  "Using the above tool results, answer the user's question:"]
        return "\n".join(parts)
