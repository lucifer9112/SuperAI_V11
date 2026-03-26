"""
SuperAI V12 — backend/cognitive/bdi_engine.py

BDI (Belief-Desire-Intention) Cognitive Engine.
Tracks agent mental states: beliefs about the world, desires (goals),
and committed intentions with plans.

Inspired by bdi-mental-states skill and Peking University BDI ontology.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


# ── Mental State Models ───────────────────────────────────────────

@dataclass
class Belief:
    belief_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""
    source: str = ""           # perception | inference | told
    confidence: float = 0.8
    grounded_in: str = ""      # world state reference
    created_at: float = field(default_factory=time.time)
    active: bool = True


@dataclass
class Desire:
    desire_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""
    motivated_by: List[str] = field(default_factory=list)  # belief_ids
    priority: float = 0.5
    fulfilled: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass
class Intention:
    intention_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""
    fulfills: str = ""         # desire_id
    supported_by: List[str] = field(default_factory=list)  # belief_ids
    plan_steps: List[str] = field(default_factory=list)
    status: str = "pending"    # pending | active | completed | abandoned
    created_at: float = field(default_factory=time.time)


@dataclass
class CognitiveState:
    """Snapshot of agent's full mental state."""
    beliefs: List[Belief] = field(default_factory=list)
    desires: List[Desire] = field(default_factory=list)
    intentions: List[Intention] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "beliefs": [{"id": b.belief_id, "content": b.content,
                         "confidence": b.confidence, "active": b.active}
                        for b in self.beliefs if b.active],
            "desires": [{"id": d.desire_id, "content": d.content,
                         "priority": d.priority, "fulfilled": d.fulfilled}
                        for d in self.desires],
            "intentions": [{"id": i.intention_id, "content": i.content,
                            "status": i.status, "steps": len(i.plan_steps)}
                           for i in self.intentions],
            "summary": {
                "active_beliefs": sum(1 for b in self.beliefs if b.active),
                "open_desires": sum(1 for d in self.desires if not d.fulfilled),
                "active_intentions": sum(1 for i in self.intentions if i.status == "active"),
            },
        }


# ── BDI Engine ────────────────────────────────────────────────────

_BELIEF_PROMPT = """Analyze this information and extract beliefs (facts the agent should hold true).

Context:
{context}

Current beliefs:
{current_beliefs}

Extract new beliefs. For each, output:
BELIEF: [what the agent should believe]
SOURCE: perception|inference|told
CONFIDENCE: [0.0-1.0]"""

_DESIRE_PROMPT = """Given these beliefs, what goals should the agent pursue?

Beliefs:
{beliefs}

User request:
{request}

For each goal, output:
DESIRE: [what to achieve]
PRIORITY: [0.0-1.0]
MOTIVATED_BY: [which beliefs motivate this]"""

_PLAN_PROMPT = """Create a plan to fulfill this intention.

Intention: {intention}
Supporting beliefs: {beliefs}

Break into ordered steps. For each:
STEP: [concrete action]"""


class BDICognitiveEngine:
    """
    BDI cognitive engine for rational agent reasoning.
    Maintains beliefs, generates desires, commits to intentions with plans.
    """

    def __init__(self, model_loader: Any = None) -> None:
        self._models = model_loader
        self._state = CognitiveState()
        logger.info("BDI Cognitive Engine initialized")

    @property
    def state(self) -> CognitiveState:
        return self._state

    # ── Belief Management ─────────────────────────────────────────

    def add_belief(
        self, content: str, source: str = "perception",
        confidence: float = 0.8, grounded_in: str = "",
    ) -> Belief:
        """Add a new belief to the agent's mental state."""
        # Check for conflicting beliefs
        for existing in self._state.beliefs:
            if existing.active and existing.content.lower() == content.lower():
                existing.confidence = max(existing.confidence, confidence)
                return existing

        belief = Belief(
            content=content, source=source,
            confidence=confidence, grounded_in=grounded_in,
        )
        self._state.beliefs.append(belief)
        return belief

    def revise_belief(self, belief_id: str, new_content: str = "",
                      confidence: float = -1) -> Optional[Belief]:
        """Update or deactivate a belief."""
        for b in self._state.beliefs:
            if b.belief_id == belief_id:
                if new_content:
                    b.content = new_content
                if confidence >= 0:
                    b.confidence = confidence
                if confidence == 0:
                    b.active = False
                return b
        return None

    def get_beliefs(self, active_only: bool = True) -> List[Belief]:
        if active_only:
            return [b for b in self._state.beliefs if b.active]
        return self._state.beliefs

    # ── Desire Management ─────────────────────────────────────────

    def add_desire(
        self, content: str, motivated_by: Optional[List[str]] = None,
        priority: float = 0.5,
    ) -> Desire:
        """Add a new desire/goal."""
        desire = Desire(
            content=content, priority=priority,
            motivated_by=motivated_by or [],
        )
        self._state.desires.append(desire)
        return desire

    def fulfill_desire(self, desire_id: str) -> Optional[Desire]:
        for d in self._state.desires:
            if d.desire_id == desire_id:
                d.fulfilled = True
                return d
        return None

    def get_desires(self, unfulfilled_only: bool = True) -> List[Desire]:
        if unfulfilled_only:
            return [d for d in self._state.desires if not d.fulfilled]
        return self._state.desires

    # ── Intention Management ──────────────────────────────────────

    def commit_intention(
        self, content: str, fulfills: str = "",
        supported_by: Optional[List[str]] = None,
        plan_steps: Optional[List[str]] = None,
    ) -> Intention:
        """Commit to an intention with a plan."""
        intention = Intention(
            content=content, fulfills=fulfills,
            supported_by=supported_by or [],
            plan_steps=plan_steps or [],
            status="active",
        )
        self._state.intentions.append(intention)
        return intention

    def complete_intention(self, intention_id: str) -> Optional[Intention]:
        for i in self._state.intentions:
            if i.intention_id == intention_id:
                i.status = "completed"
                if i.fulfills:
                    self.fulfill_desire(i.fulfills)
                return i
        return None

    def abandon_intention(self, intention_id: str, reason: str = "") -> Optional[Intention]:
        for i in self._state.intentions:
            if i.intention_id == intention_id:
                i.status = "abandoned"
                return i
        return None

    # ── Cognitive Cycle (AI-powered) ──────────────────────────────

    async def perceive(self, context: str) -> List[Belief]:
        """Extract beliefs from new context/perception."""
        if self._models is None:
            return self._fallback_perceive(context)

        try:
            current = "\n".join(
                f"- {b.content} (conf={b.confidence})"
                for b in self.get_beliefs()
            ) or "None"
            prompt = _BELIEF_PROMPT.format(context=context[:2000], current_beliefs=current)
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt, max_tokens=400, temperature=0.3,
            )
            return self._parse_beliefs(answer)
        except Exception as e:
            logger.warning("Perception failed", error=str(e))
            return self._fallback_perceive(context)

    async def deliberate(self, request: str) -> List[Desire]:
        """Generate desires from beliefs and user request."""
        if self._models is None:
            return self._fallback_deliberate(request)

        try:
            beliefs_text = "\n".join(
                f"- {b.content}" for b in self.get_beliefs()
            ) or "No current beliefs"
            prompt = _DESIRE_PROMPT.format(beliefs=beliefs_text, request=request[:1000])
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt, max_tokens=400, temperature=0.3,
            )
            return self._parse_desires(answer)
        except Exception as e:
            logger.warning("Deliberation failed", error=str(e))
            return self._fallback_deliberate(request)

    async def plan_for(self, intention: Intention) -> List[str]:
        """Generate plan steps for an intention."""
        if self._models is None:
            return ["Analyze requirements", "Implement solution", "Verify results"]

        try:
            beliefs_text = "\n".join(
                f"- {b.content}" for b in self.get_beliefs()
                if b.belief_id in intention.supported_by
            ) or "General knowledge"
            prompt = _PLAN_PROMPT.format(
                intention=intention.content, beliefs=beliefs_text,
            )
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt, max_tokens=300, temperature=0.3,
            )
            steps = []
            for line in answer.splitlines():
                if line.strip().upper().startswith("STEP:"):
                    steps.append(line.strip()[5:].strip())
            intention.plan_steps = steps or ["Execute the intention"]
            return intention.plan_steps
        except Exception as e:
            logger.warning("Planning failed", error=str(e))
            return ["Analyze", "Implement", "Verify"]

    # ── Tracing (backward explanation) ────────────────────────────

    def explain_intention(self, intention_id: str) -> Dict:
        """Backward trace: why did the agent commit to this intention?"""
        intention = None
        for i in self._state.intentions:
            if i.intention_id == intention_id:
                intention = i
                break
        if not intention:
            return {"error": "Intention not found"}

        desire = None
        if intention.fulfills:
            for d in self._state.desires:
                if d.desire_id == intention.fulfills:
                    desire = d
                    break

        beliefs = [b for b in self._state.beliefs
                   if b.belief_id in intention.supported_by]

        motivating_beliefs = []
        if desire:
            motivating_beliefs = [b for b in self._state.beliefs
                                  if b.belief_id in desire.motivated_by]

        return {
            "intention": intention.content,
            "fulfills_desire": desire.content if desire else None,
            "supporting_beliefs": [b.content for b in beliefs],
            "motivating_beliefs": [b.content for b in motivating_beliefs],
            "plan": intention.plan_steps,
            "chain": (
                f"Beliefs → Desire '{desire.content if desire else '?'}' "
                f"→ Intention '{intention.content}' → {len(intention.plan_steps)} steps"
            ),
        }

    # ── Parsing helpers ───────────────────────────────────────────

    def _parse_beliefs(self, text: str) -> List[Belief]:
        beliefs = []
        current: Dict = {}
        for line in text.splitlines():
            upper = line.strip().upper()
            if upper.startswith("BELIEF:"):
                if current.get("content"):
                    b = self.add_belief(
                        current["content"],
                        current.get("source", "inference"),
                        float(current.get("confidence", 0.7)),
                    )
                    beliefs.append(b)
                current = {"content": line.strip()[7:].strip()}
            elif upper.startswith("SOURCE:"):
                current["source"] = line.strip()[7:].strip().lower()
            elif upper.startswith("CONFIDENCE:"):
                try:
                    current["confidence"] = float(line.strip()[11:].strip())
                except ValueError:
                    pass
        if current.get("content"):
            b = self.add_belief(
                current["content"],
                current.get("source", "inference"),
                float(current.get("confidence", 0.7)),
            )
            beliefs.append(b)
        return beliefs

    def _parse_desires(self, text: str) -> List[Desire]:
        desires = []
        current: Dict = {}
        for line in text.splitlines():
            upper = line.strip().upper()
            if upper.startswith("DESIRE:"):
                if current.get("content"):
                    d = self.add_desire(
                        current["content"],
                        priority=float(current.get("priority", 0.5)),
                    )
                    desires.append(d)
                current = {"content": line.strip()[7:].strip()}
            elif upper.startswith("PRIORITY:"):
                try:
                    current["priority"] = float(line.strip()[9:].strip())
                except ValueError:
                    pass
        if current.get("content"):
            d = self.add_desire(current["content"],
                                priority=float(current.get("priority", 0.5)))
            desires.append(d)
        return desires

    # ── Fallbacks ─────────────────────────────────────────────────

    def _fallback_perceive(self, context: str) -> List[Belief]:
        b = self.add_belief(f"Context received: {context[:100]}", "perception", 0.6)
        return [b]

    def _fallback_deliberate(self, request: str) -> List[Desire]:
        d = self.add_desire(f"Fulfill request: {request[:100]}", priority=0.7)
        return [d]
