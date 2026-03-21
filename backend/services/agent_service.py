"""
SuperAI V11 - backend/services/agent_service.py
ReAct-style autonomous agent with shared context coordination.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.agents.coordinator import AgentCoordinator
from backend.config.settings import AgentSettings
from backend.models.schemas import AgentRunRequest, AgentRunResponse, AgentStep


@dataclass
class _AgentRun:
    agent_id: str
    goal: str
    session_id: str
    status: str = "running"
    steps: List[AgentStep] = field(default_factory=list)
    final_answer: Optional[str] = None


class AgentService:
    def __init__(
        self,
        model_loader,
        memory_svc,
        coordinator: AgentCoordinator,
        cfg: AgentSettings,
    ) -> None:
        self._models = model_loader
        self._memory = memory_svc
        self._coord = coordinator
        self.cfg = cfg

    async def run(self, req: AgentRunRequest) -> AgentRunResponse:
        agent_id = await self._coord.start_run(req.goal)
        session_id = req.session_id or str(uuid.uuid4())[:8]
        run = _AgentRun(agent_id=agent_id, goal=req.goal, session_id=session_id)

        try:
            await self._loop(run, req)
        except asyncio.CancelledError:
            run.status = "cancelled"
        except Exception as e:
            logger.exception("Agent run failed", agent_id=agent_id)
            run.status = "failed"
            run.final_answer = f"Agent failed: {e}"

        await self._coord.finish_run(agent_id, run.status, run.final_answer)

        return AgentRunResponse(
            agent_id=agent_id,
            goal=run.goal,
            session_id=session_id,
            status=run.status,
            steps=run.steps,
            final_answer=run.final_answer,
            iterations=len(run.steps),
        )

    async def get_status(self, agent_id: str) -> Dict[str, Any]:
        rec = self._coord.registry.get(agent_id)
        if not rec:
            return {"error": "not_found"}
        return {
            "agent_id": agent_id,
            "status": rec.status,
            "goal": rec.goal[:80],
            "started_at": rec.started_at,
        }

    async def cancel(self, agent_id: str) -> bool:
        rec = self._coord.registry.get(agent_id)
        if rec:
            rec.status = "cancelled"
            return True
        return False

    async def list_runs(self, session_id: str) -> List[Dict]:
        return self._coord.registry.list_all(limit=20)

    async def _loop(self, run: _AgentRun, req: AgentRunRequest) -> None:
        max_iter = min(req.max_iterations, self.cfg.max_iterations)

        for step_num in range(1, max_iter + 1):
            rec = self._coord.registry.get(run.agent_id)
            if rec and rec.status == "cancelled":
                break

            thought, action, action_input = await self._think(run.goal, run.steps, step_num, run.agent_id)

            if action == "finish":
                run.final_answer = action_input
                run.status = "completed"
                run.steps.append(
                    AgentStep(
                        step=step_num,
                        action="finish",
                        thought=thought,
                        result=action_input,
                        success=True,
                    )
                )
                break

            obs, success = await self._act(action, action_input, req.autonomy_level)

            if req.share_context and success:
                await self._coord.share_context(run.agent_id, f"step_{step_num}", obs[:200])

            run.steps.append(
                AgentStep(
                    step=step_num,
                    action=action,
                    thought=thought,
                    result=obs,
                    success=success,
                )
            )
            await asyncio.sleep(0)
        else:
            run.status = "max_iter_reached"
            run.final_answer = run.steps[-1].result if run.steps else "No result"

    async def _think(self, goal: str, history: List[AgentStep], step: int, agent_id: str):
        hist_text = "\n".join(f"Step {s.step}: [{s.action}] -> {s.result[:100]}" for s in history[-5:])

        shared = await self._coord.context.get_all()
        ctx_text = ""
        if shared:
            ctx_text = "\nShared context from other agents:\n" + "\n".join(
                f"  {k}: {str(v)[:80]}" for k, v in list(shared.items())[:5]
            )

        prompt = (
            f"You are an autonomous AI agent.\nGOAL: {goal}\n\n"
            f"HISTORY:\n{hist_text or 'None'}{ctx_text}\n\n"
            f"STEP {step}: Decide the next action.\n"
            f"Available: search_web | run_code | read_memory | finish\n\n"
            "Respond ONLY:\nThought: <reasoning>\nAction: <action>\nActionInput: <input>\n"
        )

        from backend.config.settings import settings

        model = settings.models.routing.get("agent", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
        answer, _ = await self._models.infer(model, prompt, max_tokens=256, temperature=0.3)

        thought = self._extract("Thought", answer)
        action = self._extract("Action", answer).lower().strip() or "finish"
        action_input = self._extract("ActionInput", answer)
        return thought, action, action_input

    async def _act(self, action: str, action_input: str, autonomy: int):
        if action == "search_web":
            return await self._search(action_input), True
        if action == "run_code":
            return await self._run_code(action_input), True
        if action == "read_memory":
            return await self._read_memory(action_input), True
        return f"Unknown action: {action}", False

    async def _search(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(d.text(query, max_results=3))
            return "\n".join(f"- {r['title']}: {r['body'][:200]}" for r in results)
        except Exception as e:
            return f"Search failed: {e}"

    async def _run_code(self, code: str) -> str:
        import subprocess
        import sys

        try:
            r = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=self.cfg.tool_timeout,
            )
            return (r.stdout or r.stderr)[:500]
        except Exception as e:
            return f"Code error: {e}"

    async def _read_memory(self, query: str) -> str:
        from backend.models.schemas import MemorySearchRequest

        try:
            results = await self._memory.search(MemorySearchRequest(query=query, top_k=3))
            return "\n".join(e.content[:150] for e in results.entries) or "Nothing found."
        except Exception:
            return "Memory unavailable."

    @staticmethod
    def _extract(key: str, text: str) -> str:
        import re

        m = re.search(rf"{key}:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        return m.group(1).strip() if m else ""
