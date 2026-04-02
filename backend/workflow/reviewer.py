"""
SuperAI V11 — backend/workflow/reviewer.py

Review phase: evaluates agent output against the original plan.
Scores issues by severity (critical/warning/info).
Critical issues block progress.

Inspired by Superpowers' requesting-code-review + verification-before-completion.
"""
from __future__ import annotations

from typing import Any, List, Optional

from loguru import logger

from backend.workflow.models import IssueSeverity, ReviewIssue, ReviewResult


_REVIEW_PROMPT = """You are a senior code reviewer performing a two-stage review.

STAGE 1 - Spec Compliance:
Original task: {task_description}
Expected verification: {verification}

STAGE 2 - Code Quality:
Check for: correctness, error handling, edge cases, readability, security.

Agent output to review:
{output}

For each issue found, output EXACTLY:
SEVERITY: critical|warning|info
ISSUE: [description]
LOCATION: [where in the output]
FIX: [suggested fix]

End with:
OVERALL: pass|fail
SCORE: [0.0 to 1.0]
SUMMARY: [one sentence]"""


class WorkflowReviewer:
    """Reviews agent output with 2-stage evaluation."""

    def __init__(self, model_loader: Any = None) -> None:
        self._models = model_loader

    async def review(
        self,
        output: str,
        task_description: str = "",
        verification: str = "",
    ) -> ReviewResult:
        """Run 2-stage review on agent output."""
        if self._models is None:
            return self._heuristic_review(output, task_description)

        try:
            prompt = _REVIEW_PROMPT.format(
                task_description=task_description or "Not specified",
                verification=verification or "Not specified",
                output=output[:2000],
            )
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt,
                max_tokens=600, temperature=0.2,
            )
            if self._looks_degraded(answer):
                return self._heuristic_review(output, task_description)
            return self._parse_review(answer)
        except Exception as e:
            logger.warning("Review failed, using heuristic", error=str(e))
            return self._heuristic_review(output, task_description)

    # ── Parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_review(text: str) -> ReviewResult:
        issues: List[ReviewIssue] = []
        passed = True
        score = 0.5
        summary = ""

        current_issue: dict = {}

        for line in text.splitlines():
            stripped = line.strip()
            upper = stripped.upper()

            if upper.startswith("SEVERITY:"):
                if current_issue.get("description"):
                    sev_str = current_issue.get("severity", "info").lower()
                    sev = IssueSeverity.CRITICAL if "critical" in sev_str \
                        else IssueSeverity.WARNING if "warning" in sev_str \
                        else IssueSeverity.INFO
                    issues.append(ReviewIssue(
                        severity=sev,
                        description=current_issue.get("description", ""),
                        location=current_issue.get("location", ""),
                        suggestion=current_issue.get("fix", ""),
                    ))
                current_issue = {"severity": stripped[9:].strip()}
            elif upper.startswith("ISSUE:"):
                current_issue["description"] = stripped[6:].strip()
            elif upper.startswith("LOCATION:"):
                current_issue["location"] = stripped[9:].strip()
            elif upper.startswith("FIX:"):
                current_issue["fix"] = stripped[4:].strip()
            elif upper.startswith("OVERALL:"):
                val = stripped[8:].strip().lower()
                passed = val != "fail"
            elif upper.startswith("SCORE:"):
                try:
                    score = float(stripped[6:].strip())
                except ValueError:
                    pass
            elif upper.startswith("SUMMARY:"):
                summary = stripped[8:].strip()

        # Flush last issue
        if current_issue.get("description"):
            sev_str = current_issue.get("severity", "info").lower()
            sev = IssueSeverity.CRITICAL if "critical" in sev_str \
                else IssueSeverity.WARNING if "warning" in sev_str \
                else IssueSeverity.INFO
            issues.append(ReviewIssue(
                severity=sev,
                description=current_issue.get("description", ""),
                location=current_issue.get("location", ""),
                suggestion=current_issue.get("fix", ""),
            ))

        # Critical issues force fail
        if any(i.severity == IssueSeverity.CRITICAL for i in issues):
            passed = False

        return ReviewResult(
            passed=passed, issues=issues,
            summary=summary or ("Review passed" if passed else "Review found issues"),
            score=max(0.0, min(1.0, score)),
        )

    # ── Heuristic fallback ────────────────────────────────────────

    @staticmethod
    def _heuristic_review(output: str, task_description: str) -> ReviewResult:
        issues: List[ReviewIssue] = []

        if not output or len(output.strip()) < 10:
            issues.append(ReviewIssue(
                severity=IssueSeverity.CRITICAL,
                description="Agent produced empty or very short output",
            ))
        if "error" in output.lower() or "traceback" in output.lower():
            issues.append(ReviewIssue(
                severity=IssueSeverity.WARNING,
                description="Output contains error indicators",
            ))
        if len(output) > 5000:
            issues.append(ReviewIssue(
                severity=IssueSeverity.INFO,
                description="Output is unusually long, may contain verbose content",
            ))

        has_critical = any(i.severity == IssueSeverity.CRITICAL for i in issues)
        score = 0.2 if has_critical else 0.9 - (len(issues) * 0.15)

        return ReviewResult(
            passed=not has_critical,
            issues=issues,
            summary="Heuristic review (no model available)",
            score=max(0.0, min(1.0, score)),
        )

    @staticmethod
    def _looks_degraded(text: str) -> bool:
        lowered = text.lower()
        return "degraded model mode" in lowered or "server is healthy" in lowered
