"""SuperAI V11 — backend/core/task_router.py — Task classifier + model selector."""
from __future__ import annotations
import re
from typing import Dict
from backend.models.schemas import TaskType


class TaskRouter:
    _PATTERNS: list[tuple[TaskType, list[str]]] = [
        (TaskType.CODE, [
            r"\bcode\b", r"\bfunction\b", r"\bclass\b", r"\bscript\b",
            r"\bpython\b", r"\bjavascript\b", r"\btypescript\b", r"\brust\b",
            r"\bdebug\b", r"\brefactor\b", r"\balgorithm\b", r"\bsql\b",
        ]),
        (TaskType.MATH, [
            r"\bmath\b", r"\bsolve\b", r"\bequation\b", r"\bcalculat",
            r"\bintegral\b", r"\bderivative\b", r"\bprobability\b",
            r"\bstatistic\b", r"\bformula\b", r"[=\+\-\*\/]\s*\d",
        ]),
        (TaskType.VISION, [
            r"\bimage\b", r"\bphoto\b", r"\bpicture\b", r"\bscreenshot\b",
            r"\bdescribe\s+this\b", r"\bwhat.+see\b", r"\bocr\b",
        ]),
        (TaskType.DOCUMENT, [
            r"\bdocument\b", r"\bpdf\b", r"\bfile\b", r"\bsummariz",
            r"\bextract\b", r"\bspreadsheet\b", r"\baccording\s+to\b",
        ]),
        (TaskType.VOICE, [
            r"\bspeak\b", r"\btts\b", r"\btext.to.speech\b", r"\bsay\s+this\b",
        ]),
        (TaskType.SEARCH, [
            r"\bsearch\b", r"\blatest\b", r"\brecent\b", r"\bnews\b",
            r"\btoday\b", r"\bcurrent\b", r"\bwhat\s+happened\b",
        ]),
        (TaskType.AGENT, [
            r"\bautonomously\b", r"\bdo\s+for\s+me\b", r"\bstep.by.step.*execute\b",
            r"\bgoal\s*:\b", r"\bplan\s+and\s+execute\b",
        ]),
    ]

    def __init__(self, routing_cfg: Dict[str, str]) -> None:
        self._routing  = routing_cfg
        self._compiled = [
            (t, [re.compile(p, re.IGNORECASE) for p in pats])
            for t, pats in self._PATTERNS
        ]

    def route(self, prompt: str) -> TaskType:
        for task_type, patterns in self._compiled:
            if any(p.search(prompt) for p in patterns):
                return task_type
        return TaskType.CHAT

    def select_model(self, task_type: TaskType) -> str:
        return (
            self._routing.get(task_type.value)
            or self._routing.get("chat")
            or "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        )
