"""
SuperAI V11 — backend/debugging/debugger.py

Systematic Debugging Engine: 4-phase root cause analysis.
1. Reproduce — analyze error, identify reproduction steps
2. Isolate — narrow down to root cause
3. Fix — generate targeted fix
4. Verify — propose verification steps

Inspired by Superpowers' systematic-debugging skill.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class DebugPhaseResult:
    phase: str
    analysis: str
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)


@dataclass
class DebugReport:
    error_description: str
    phases: List[DebugPhaseResult] = field(default_factory=list)
    root_cause: str = ""
    proposed_fix: str = ""
    verification_steps: List[str] = field(default_factory=list)
    overall_confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "error_description": self.error_description[:200],
            "root_cause": self.root_cause,
            "proposed_fix": self.proposed_fix,
            "verification_steps": self.verification_steps,
            "phases": [
                {"phase": p.phase, "analysis": p.analysis[:300],
                 "confidence": p.confidence}
                for p in self.phases
            ],
            "overall_confidence": self.overall_confidence,
        }


_PHASE_PROMPTS = {
    "reproduce": """You are a systematic debugger in Phase 1: REPRODUCE.

Error description:
{error}

Code context:
{code}

Analyze the error and determine:
1. What exact steps reproduce this error?
2. What is the expected vs actual behavior?
3. Is this error consistent or intermittent?

Provide your analysis and list reproduction steps.""",

    "isolate": """You are a systematic debugger in Phase 2: ISOLATE.

Error description:
{error}

Code context:
{code}

Previous analysis (reproduce):
{prev}

Narrow down the root cause:
1. Which specific component/function is failing?
2. What is the exact condition that triggers the bug?
3. Rule out at least 2 other possible causes and explain why.

State the root cause clearly in one sentence at the end.""",

    "fix": """You are a systematic debugger in Phase 3: FIX.

Error description:
{error}

Root cause:
{root_cause}

Code context:
{code}

Generate a minimal, targeted fix:
1. Show the exact code change needed (as small as possible)
2. Explain why this fix addresses the root cause
3. Note any side effects or risks

Keep changes minimal — fix only the bug, nothing else.""",

    "verify": """You are a systematic debugger in Phase 4: VERIFY.

Error description:
{error}

Applied fix:
{fix}

Propose verification steps:
1. How to confirm the fix works (test cases)
2. How to ensure no regression (what else to check)
3. Edge cases to test

List 3-5 concrete verification steps.""",
}


class SystematicDebugger:
    """4-phase systematic debugging engine."""

    def __init__(self, model_loader: Any = None) -> None:
        self._models = model_loader

    async def full_debug(
        self, error: str, code: str = "", max_attempts: int = 3,
    ) -> DebugReport:
        """Run all 4 phases of systematic debugging."""
        report = DebugReport(error_description=error)

        # Phase 1: Reproduce
        reproduce = await self._run_phase(
            "reproduce", error=error, code=code,
        )
        report.phases.append(reproduce)

        # Phase 2: Isolate
        isolate = await self._run_phase(
            "isolate", error=error, code=code,
            prev=reproduce.analysis,
        )
        report.phases.append(isolate)
        report.root_cause = self._extract_root_cause(isolate.analysis)

        # Phase 3: Fix
        fix = await self._run_phase(
            "fix", error=error, code=code,
            root_cause=report.root_cause,
        )
        report.phases.append(fix)
        report.proposed_fix = fix.analysis

        # Phase 4: Verify
        verify = await self._run_phase(
            "verify", error=error, code=code,
            fix=fix.analysis,
        )
        report.phases.append(verify)
        report.verification_steps = verify.suggestions

        # Overall confidence
        if report.phases:
            report.overall_confidence = sum(
                p.confidence for p in report.phases
            ) / len(report.phases)

        return report

    async def isolate_only(
        self, error: str, code: str = "",
    ) -> DebugPhaseResult:
        """Run just the isolate phase for quick root cause analysis."""
        reproduce = await self._run_phase("reproduce", error=error, code=code)
        isolate = await self._run_phase(
            "isolate", error=error, code=code,
            prev=reproduce.analysis,
        )
        return isolate

    # ── Phase execution ───────────────────────────────────────────

    async def _run_phase(self, phase: str, **kwargs) -> DebugPhaseResult:
        """Execute a single debug phase."""
        prompt_template = _PHASE_PROMPTS.get(phase, "")
        if not prompt_template:
            return DebugPhaseResult(phase=phase, analysis="Unknown phase")

        # Fill in template with available kwargs
        prompt = prompt_template.format(
            error=kwargs.get("error", ""),
            code=kwargs.get("code", "")[:2000],
            prev=kwargs.get("prev", ""),
            root_cause=kwargs.get("root_cause", ""),
            fix=kwargs.get("fix", ""),
        )

        if self._models is None:
            return self._fallback_phase(phase, kwargs.get("error", ""))

        try:
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt,
                max_tokens=500, temperature=0.3,
            )
            if self._looks_degraded(answer):
                return self._fallback_phase(phase, kwargs.get("error", ""))
            suggestions = self._extract_numbered_items(answer)
            return DebugPhaseResult(
                phase=phase,
                analysis=answer,
                confidence=0.6,
                suggestions=suggestions,
            )
        except Exception as e:
            logger.warning(f"Debug phase {phase} failed", error=str(e))
            return self._fallback_phase(phase, kwargs.get("error", ""))

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _extract_root_cause(analysis: str) -> str:
        """Try to extract root cause from the isolate analysis."""
        lines = analysis.strip().splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line and len(line) > 20:
                return line
        return analysis[:200] if analysis else "Could not determine root cause"

    @staticmethod
    def _looks_degraded(text: str) -> bool:
        lowered = text.lower()
        return "degraded model mode" in lowered or "server is healthy" in lowered

    @staticmethod
    def _extract_numbered_items(text: str) -> List[str]:
        items = []
        for line in text.splitlines():
            line = line.strip()
            if line and line[0].isdigit() and "." in line[:4]:
                items.append(line.split(".", 1)[-1].strip())
            elif line.startswith("- "):
                items.append(line[2:])
        return items[:5]

    @staticmethod
    def _fallback_phase(phase: str, error: str) -> DebugPhaseResult:
        fallbacks = {
            "reproduce": DebugPhaseResult(
                phase="reproduce",
                analysis=f"Error reported: {error}. Check input data and preconditions.",
                confidence=0.3,
                suggestions=["Check error logs", "Verify input data", "Test in isolation"],
            ),
            "isolate": DebugPhaseResult(
                phase="isolate",
                analysis="Root cause analysis requires model inference. Check the stack trace for the originating function.",
                confidence=0.2,
                suggestions=["Add detailed logging", "Binary search through recent changes"],
            ),
            "fix": DebugPhaseResult(
                phase="fix",
                analysis="Fix generation requires model inference. Apply defensive coding around the identified error point.",
                confidence=0.2,
                suggestions=["Add input validation", "Add try/except", "Add null checks"],
            ),
            "verify": DebugPhaseResult(
                phase="verify",
                analysis="Verification steps:",
                confidence=0.3,
                suggestions=["Run unit tests", "Test the specific failing case", "Check for regressions", "Run integration tests"],
            ),
        }
        return fallbacks.get(phase, DebugPhaseResult(phase=phase, analysis="Unknown phase"))
