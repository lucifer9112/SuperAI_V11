"""
SuperAI V11 — backend/evaluation/llm_judge.py

LLM-as-Judge Evaluator: multi-criteria evaluation engine.
Supports rubric-based scoring, pairwise comparison, and calibration.

Inspired by evaluation + advanced-evaluation skills.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class JudgeCriterion:
    name: str
    description: str
    weight: float = 1.0
    score: float = 0.0       # 0.0 – 1.0


@dataclass
class JudgeResult:
    overall_score: float = 0.0
    criteria: List[JudgeCriterion] = field(default_factory=list)
    explanation: str = ""
    verdict: str = ""        # pass | fail | needs_improvement
    pairwise_winner: str = ""  # for pairwise comparison


_RUBRIC_PROMPT = """You are an LLM-as-Judge evaluator. Score this output on each criterion.

Output to evaluate:
{output}

Task context:
{task}

{reference_section}

Score each criterion from 0.0 to 1.0:
{criteria_list}

For each criterion, output EXACTLY:
CRITERION: [name]
SCORE: [0.0-1.0]
REASON: [one sentence]

End with:
VERDICT: pass|fail|needs_improvement
EXPLANATION: [overall assessment in one sentence]"""

_PAIRWISE_PROMPT = """You are an LLM-as-Judge comparing two outputs.

Task: {task}

Output A:
{output_a}

Output B:
{output_b}

Which output is better? Consider: accuracy, completeness, clarity, and relevance.
Output EXACTLY:
WINNER: A|B|TIE
REASON: [one sentence explanation]"""


# ── Default Rubrics ───────────────────────────────────────────────

DEFAULT_CRITERIA = [
    JudgeCriterion("accuracy", "Are facts correct and claims verifiable?"),
    JudgeCriterion("completeness", "Does it answer the full question?"),
    JudgeCriterion("relevance", "Is irrelevant information excluded?"),
    JudgeCriterion("clarity", "Is it well-structured and easy to understand?"),
    JudgeCriterion("safety", "Is the output safe and appropriate?"),
]

CODE_CRITERIA = [
    JudgeCriterion("correctness", "Does the code work as intended?"),
    JudgeCriterion("style", "Does it follow best practices and conventions?"),
    JudgeCriterion("efficiency", "Is it performant without unnecessary waste?"),
    JudgeCriterion("security", "Are there security vulnerabilities?"),
    JudgeCriterion("maintainability", "Is it readable and maintainable?"),
]


class LLMJudge:
    """Multi-criteria LLM-as-Judge evaluation engine."""

    def __init__(self, model_loader: Any = None) -> None:
        self._models = model_loader

    async def evaluate(
        self,
        output: str,
        task: str = "",
        reference: str = "",
        criteria: Optional[List[JudgeCriterion]] = None,
    ) -> JudgeResult:
        """Evaluate output against rubric criteria."""
        criteria = criteria or [JudgeCriterion(c.name, c.description, c.weight)
                                for c in DEFAULT_CRITERIA]

        if self._models is None:
            return self._heuristic_evaluate(output, criteria)

        try:
            criteria_list = "\n".join(
                f"- {c.name}: {c.description}" for c in criteria
            )
            ref_section = f"Reference answer:\n{reference}" if reference else ""
            prompt = _RUBRIC_PROMPT.format(
                output=output[:2000], task=task or "General evaluation",
                reference_section=ref_section, criteria_list=criteria_list,
            )
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt, max_tokens=600, temperature=0.2,
            )
            return self._parse_rubric(answer, criteria)
        except Exception as e:
            logger.warning("LLM judge failed", error=str(e))
            return self._heuristic_evaluate(output, criteria)

    async def pairwise(
        self,
        output_a: str,
        output_b: str,
        task: str = "",
    ) -> JudgeResult:
        """Compare two outputs head-to-head."""
        if self._models is None:
            return self._heuristic_pairwise(output_a, output_b)

        try:
            prompt = _PAIRWISE_PROMPT.format(
                task=task or "General comparison",
                output_a=output_a[:1000], output_b=output_b[:1000],
            )
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt, max_tokens=200, temperature=0.2,
            )
            return self._parse_pairwise(answer)
        except Exception as e:
            logger.warning("Pairwise comparison failed", error=str(e))
            return self._heuristic_pairwise(output_a, output_b)

    async def evaluate_code(
        self, code: str, task: str = "",
    ) -> JudgeResult:
        """Evaluate code using code-specific criteria."""
        criteria = [JudgeCriterion(c.name, c.description, c.weight)
                     for c in CODE_CRITERIA]
        return await self.evaluate(code, task=task, criteria=criteria)

    # ── Parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_rubric(text: str, criteria: List[JudgeCriterion]) -> JudgeResult:
        scores: Dict[str, tuple] = {}
        verdict = "needs_improvement"
        explanation = ""

        current_name = ""
        for line in text.splitlines():
            stripped = line.strip()
            upper = stripped.upper()
            if upper.startswith("CRITERION:"):
                current_name = stripped[10:].strip().lower()
            elif upper.startswith("SCORE:"):
                try:
                    score = float(stripped[6:].strip())
                    if current_name:
                        scores[current_name] = score
                except ValueError:
                    pass
            elif upper.startswith("VERDICT:"):
                verdict = stripped[8:].strip().lower()
            elif upper.startswith("EXPLANATION:"):
                explanation = stripped[12:].strip()

        for c in criteria:
            c.score = scores.get(c.name.lower(), 0.5)

        total_weight = sum(c.weight for c in criteria) or 1.0
        overall = sum(c.score * c.weight for c in criteria) / total_weight

        return JudgeResult(
            overall_score=round(overall, 3),
            criteria=criteria,
            explanation=explanation,
            verdict=verdict,
        )

    @staticmethod
    def _parse_pairwise(text: str) -> JudgeResult:
        winner = "TIE"
        reason = ""
        for line in text.splitlines():
            upper = line.strip().upper()
            if upper.startswith("WINNER:"):
                w = line.strip()[7:].strip().upper()
                if "A" in w:
                    winner = "A"
                elif "B" in w:
                    winner = "B"
                else:
                    winner = "TIE"
            elif upper.startswith("REASON:"):
                reason = line.strip()[7:].strip()
        return JudgeResult(
            overall_score=1.0 if winner != "TIE" else 0.5,
            explanation=reason,
            verdict=f"winner_{winner}",
            pairwise_winner=winner,
        )

    # ── Heuristic fallback ────────────────────────────────────────

    @staticmethod
    def _heuristic_evaluate(
        output: str, criteria: List[JudgeCriterion],
    ) -> JudgeResult:
        length = len(output.split())
        for c in criteria:
            if c.name in ("accuracy", "correctness"):
                c.score = 0.6 if length > 10 else 0.3
            elif c.name in ("completeness",):
                c.score = min(1.0, length / 100)
            elif c.name in ("relevance", "clarity"):
                c.score = 0.7 if 10 < length < 500 else 0.2 if length <= 10 else 0.5
            elif c.name in ("safety", "security"):
                unsafe = any(w in output.lower() for w in ["eval(", "exec(", "password"])
                c.score = 0.3 if unsafe else 0.9
            else:
                c.score = 0.5

        total_weight = sum(c.weight for c in criteria) or 1.0
        overall = sum(c.score * c.weight for c in criteria) / total_weight
        verdict = "pass" if overall >= 0.7 else "fail" if overall < 0.4 else "needs_improvement"

        return JudgeResult(
            overall_score=round(overall, 3), criteria=criteria,
            explanation="Heuristic evaluation (no model)", verdict=verdict,
        )

    @staticmethod
    def _heuristic_pairwise(output_a: str, output_b: str) -> JudgeResult:
        len_a, len_b = len(output_a.split()), len(output_b.split())
        winner = "A" if len_a > len_b * 1.2 else "B" if len_b > len_a * 1.2 else "TIE"
        return JudgeResult(
            overall_score=0.5, explanation="Heuristic: longer response selected",
            verdict=f"winner_{winner}", pairwise_winner=winner,
        )
