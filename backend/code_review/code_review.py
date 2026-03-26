"""
SuperAI V12 — backend/code_review/code_review.py

Code Review Engine: evaluates code or diffs against configurable criteria.
Returns issues with severity levels and suggested fixes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class CodeIssue:
    severity: str          # critical | warning | info
    category: str          # correctness | style | security | performance
    description: str
    line: int = 0
    suggestion: str = ""


@dataclass
class CodeReviewResult:
    total_issues: int = 0
    critical: int = 0
    warnings: int = 0
    info: int = 0
    issues: List[CodeIssue] = field(default_factory=list)
    summary: str = ""
    score: float = 0.0     # 0.0 (terrible) – 1.0 (perfect)


_REVIEW_PROMPT = """You are an expert code reviewer. Review this code for:
1. **Correctness** — bugs, logic errors, edge cases
2. **Style** — readability, naming, formatting
3. **Security** — injection, data leaks, unsafe operations
4. **Performance** — inefficiency, unnecessary allocations

Code to review:
```
{code}
```

{context}

For each issue found, output EXACTLY:
SEVERITY: critical|warning|info
CATEGORY: correctness|style|security|performance
LINE: [line number or 0]
ISSUE: [description]
FIX: [suggested fix]

End with:
SCORE: [0.0 to 1.0]
SUMMARY: [one sentence overall assessment]"""


_SUGGEST_PROMPT = """You are an expert code reviewer. Suggest improvements for:
```
{code}
```

Focus on: {focus}

Output up to 5 specific, actionable suggestions. Format:
1. [suggestion]
2. [suggestion]
..."""


class CodeReviewEngine:
    """Reviews code and provides severity-scored feedback."""

    def __init__(self, model_loader: Any = None) -> None:
        self._models = model_loader

    async def review(
        self,
        code: str,
        language: str = "",
        context: str = "",
        max_issues: int = 20,
    ) -> CodeReviewResult:
        """Review code and return structured issues."""
        if self._models is None:
            return self._heuristic_review(code)

        try:
            ctx = f"Language: {language}\nContext: {context}" if language else ""
            prompt = _REVIEW_PROMPT.format(code=code[:3000], context=ctx)
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt,
                max_tokens=800, temperature=0.2,
            )
            return self._parse_review(answer, max_issues)
        except Exception as e:
            logger.warning("Code review failed", error=str(e))
            return self._heuristic_review(code)

    async def suggest(
        self,
        code: str,
        focus: str = "general improvements",
    ) -> List[str]:
        """Get improvement suggestions for code."""
        if self._models is None:
            return self._heuristic_suggestions(code)

        try:
            prompt = _SUGGEST_PROMPT.format(code=code[:3000], focus=focus)
            answer, _ = await self._models.infer(
                model_name="", prompt=prompt,
                max_tokens=400, temperature=0.4,
            )
            return self._parse_suggestions(answer)
        except Exception as e:
            logger.warning("Suggestion generation failed", error=str(e))
            return self._heuristic_suggestions(code)

    # ── Parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_review(text: str, max_issues: int) -> CodeReviewResult:
        issues: List[CodeIssue] = []
        score = 0.5
        summary = ""
        current: Dict = {}

        for line in text.splitlines():
            stripped = line.strip()
            upper = stripped.upper()

            if upper.startswith("SEVERITY:"):
                if current.get("description"):
                    issues.append(CodeIssue(
                        severity=current.get("severity", "info"),
                        category=current.get("category", "correctness"),
                        description=current.get("description", ""),
                        line=int(current.get("line", 0)),
                        suggestion=current.get("fix", ""),
                    ))
                current = {"severity": stripped[9:].strip().lower()}
            elif upper.startswith("CATEGORY:"):
                current["category"] = stripped[9:].strip().lower()
            elif upper.startswith("LINE:"):
                try:
                    current["line"] = int(stripped[5:].strip())
                except ValueError:
                    current["line"] = 0
            elif upper.startswith("ISSUE:"):
                current["description"] = stripped[6:].strip()
            elif upper.startswith("FIX:"):
                current["fix"] = stripped[4:].strip()
            elif upper.startswith("SCORE:"):
                try:
                    score = float(stripped[6:].strip())
                except ValueError:
                    pass
            elif upper.startswith("SUMMARY:"):
                summary = stripped[8:].strip()

        # Flush last issue
        if current.get("description"):
            issues.append(CodeIssue(
                severity=current.get("severity", "info"),
                category=current.get("category", "correctness"),
                description=current.get("description", ""),
                line=int(current.get("line", 0)),
                suggestion=current.get("fix", ""),
            ))

        issues = issues[:max_issues]
        critical = sum(1 for i in issues if i.severity == "critical")
        warnings = sum(1 for i in issues if i.severity == "warning")
        info_count = sum(1 for i in issues if i.severity == "info")

        return CodeReviewResult(
            total_issues=len(issues),
            critical=critical,
            warnings=warnings,
            info=info_count,
            issues=issues,
            summary=summary or f"Found {len(issues)} issues",
            score=max(0.0, min(1.0, score)),
        )

    @staticmethod
    def _parse_suggestions(text: str) -> List[str]:
        suggestions = []
        for line in text.strip().splitlines():
            line = line.strip()
            if line and line[0].isdigit() and "." in line[:4]:
                suggestions.append(line.split(".", 1)[-1].strip())
            elif line.startswith("- "):
                suggestions.append(line[2:])
        return suggestions[:5]

    # ── Heuristic fallback ────────────────────────────────────────

    @staticmethod
    def _heuristic_review(code: str) -> CodeReviewResult:
        issues: List[CodeIssue] = []
        lines = code.splitlines()

        for i, line in enumerate(lines, 1):
            if "eval(" in line or "exec(" in line:
                issues.append(CodeIssue("critical", "security", f"Unsafe eval/exec at line {i}", i, "Use safer alternatives"))
            if "import os" in line and "system" in code:
                issues.append(CodeIssue("warning", "security", f"os.system usage near line {i}", i, "Use subprocess.run instead"))
            if len(line) > 120:
                issues.append(CodeIssue("info", "style", f"Line {i} exceeds 120 chars", i, "Break into shorter lines"))
            if "TODO" in line or "HACK" in line or "FIXME" in line:
                issues.append(CodeIssue("info", "style", f"Unresolved marker at line {i}", i, "Address or remove"))
            if "password" in line.lower() and "=" in line and ("'" in line or '"' in line):
                issues.append(CodeIssue("critical", "security", f"Possible hardcoded password at line {i}", i, "Use environment variables"))

        score = max(0.0, 1.0 - len(issues) * 0.1)
        return CodeReviewResult(
            total_issues=len(issues),
            critical=sum(1 for i in issues if i.severity == "critical"),
            warnings=sum(1 for i in issues if i.severity == "warning"),
            info=sum(1 for i in issues if i.severity == "info"),
            issues=issues[:20],
            summary="Heuristic review (no model available)",
            score=score,
        )

    @staticmethod
    def _heuristic_suggestions(code: str) -> List[str]:
        suggestions = []
        if "try:" not in code:
            suggestions.append("Add error handling with try/except blocks")
        if '"""' not in code and "'''" not in code:
            suggestions.append("Add docstrings to functions and classes")
        if "logging" not in code and "logger" not in code:
            suggestions.append("Add logging for better observability")
        if "async " not in code and "await " not in code:
            suggestions.append("Consider async patterns for I/O operations")
        if not suggestions:
            suggestions.append("Code looks good — consider adding type hints")
        return suggestions
