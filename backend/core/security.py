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
        if self.cfg.prompt_injection_guard:
            for pat in self._inj_re:
                if pat.search(prompt):
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

    async def scan_code(self, code: str, language: str = "python") -> List[str]:
        if not self.cfg.bandit_scan or language.lower() != "python":
            return []
        issues: List[str] = []
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write(code)
            tmp = f.name
        try:
            r = subprocess.run(["bandit", "-r", tmp, "-f", "txt", "-q"],
                               capture_output=True, text=True, timeout=15)
            issues = [l.strip() for l in r.stdout.splitlines() if l.startswith(">>")]
        except Exception as e:
            logger.warning("bandit scan skipped", error=str(e))
        finally:
            Path(tmp).unlink(missing_ok=True)
        return issues
