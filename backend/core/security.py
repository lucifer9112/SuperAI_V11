"""SuperAI V11 — backend/core/security.py — Input/output security."""
from __future__ import annotations
import re, subprocess, tempfile, unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger
from backend.config.settings import SecuritySettings

_INJ = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(everything|all)",
    r"you\s+are\s+now\s+(?!SuperAI)",
    r"pretend\s+you\s+are",
    r"jailbreak", r"DAN\s+mode", r"developer\s+mode",
    r"<\s*script\s*>", r"system\s*:\s*ignore",
]
_HARM = [
    r"how\s+to\s+make\s+(?:a\s+)?bomb",
    r"synthesis\s+of\s+(?:meth|cocaine|heroin)",
    r"(?:make|build|create)\s+(?:an?\s+)?(?:explosive|bomb|weapon)",
    r"(?:make|build|create)\s+explosives?",
    r"how\s+to\s+(?:hack|break\s+into|bypass)\b",
    r"(?:weapon|explosive|drug)\s+synthesis",
]

_HEURISTIC_CODE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\beval\s*\("), "Use of eval() can execute untrusted input."),
    (re.compile(r"\bexec\s*\("), "Use of exec() can execute untrusted code."),
    (re.compile(r"os\.system\s*\("), "os.system() may execute shell commands unsafely."),
    (re.compile(r"subprocess\.(?:run|Popen|call)\s*\([^)]*shell\s*=\s*True", re.IGNORECASE | re.DOTALL), "subprocess with shell=True increases command injection risk."),
    (re.compile(r"yaml\.load\s*\("), "yaml.load() without a safe loader can be unsafe."),
    (re.compile(r"pickle\.loads?\s*\("), "pickle deserialization can execute arbitrary code."),
    (re.compile(r"(password|secret|token|api_key)\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE), "Possible hardcoded secret found in source."),
]


def _normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


class SecurityEngine:
    def __init__(self, cfg: SecuritySettings) -> None:
        self.cfg = cfg
        self._inj_re  = [re.compile(p, re.IGNORECASE) for p in _INJ]
        self._harm_re = [re.compile(p, re.IGNORECASE) for p in _HARM]

    def validate(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.cfg.enabled:
            return None
        # Normalize Unicode to prevent homoglyph bypass attacks
        normalized = _normalize_text(prompt)
        if self.cfg.prompt_injection_guard:
            for pat in self._inj_re:
                if pat.search(normalized):
                    logger.warning("Injection blocked", pattern=pat.pattern[:40])
                    return {"reason": "prompt_injection", "pattern": pat.pattern[:40]}
        return None

    def filter_output(self, text: str) -> str:
        if not self.cfg.output_filter:
            return text
        normalized = _normalize_text(text)
        for pat in self._harm_re:
            if pat.search(normalized):
                return "[Response filtered by safety system]"
        return text

    def _heuristic_scan_code(self, code: str) -> List[str]:
        issues: List[str] = []
        for pattern, message in _HEURISTIC_CODE_PATTERNS:
            if pattern.search(code):
                issues.append(message)
        return issues

    async def scan_code(self, code: str, language: str = "python") -> List[str]:
        if not self.cfg.bandit_scan or language.lower() != "python":
            return self._heuristic_scan_code(code) if language.lower() == "python" else []
        issues: List[str] = []
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write(code)
            tmp = f.name
        try:
            import asyncio
            r = await asyncio.to_thread(
                subprocess.run,
                ["bandit", "-r", tmp, "-f", "txt", "-q"],
                capture_output=True, text=True, timeout=15,
            )
            issues = [l.strip() for l in r.stdout.splitlines() if l.startswith(">>")]
        except FileNotFoundError:
            logger.warning("bandit not installed, skipping static scan. Run: pip install bandit")
            issues = self._heuristic_scan_code(code)
        except Exception as e:
            logger.warning("bandit scan failed", error=str(e))
            issues = self._heuristic_scan_code(code)
        finally:
            Path(tmp).unlink(missing_ok=True)
        return issues
