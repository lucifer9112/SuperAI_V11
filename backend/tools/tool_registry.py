"""
SuperAI V11 — backend/tools/tool_registry.py
STEP 2: Tool Calling Engine — Registry + Schema + Selector
"""
from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from loguru import logger


@dataclass
class ToolDef:
    name:        str
    description: str
    parameters:  Dict[str, Any]  # JSON Schema
    handler:     Callable
    category:    str  = "general"
    safe:        bool = True
    timeout_s:   int  = 30


@dataclass
class ToolResult:
    tool_name:    str
    success:      bool
    output:       str
    error:        Optional[str] = None
    exec_ms:      float = 0.0

    def to_context(self) -> str:
        return (f"[{self.tool_name}]\n{self.output}"
                if self.success else
                f"[{self.tool_name} FAILED] {self.error}")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolDef] = {}

    def register(self, t: ToolDef) -> None:
        self._tools[t.name] = t

    def get(self, name: str) -> Optional[ToolDef]:
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolDef]:
        tools = list(self._tools.values())
        return [t for t in tools if t.category == category] if category else tools

    def schema_prompt(self) -> str:
        lines = ["Available tools:"]
        for t in self._tools.values():
            params = list(t.parameters.get("properties", {}).keys())
            lines.append(f"  - {t.name}({', '.join(params)}): {t.description}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._tools)


class ToolSelector:
    _KEYWORDS: Dict[str, List[str]] = {
        "web_search":   ["search","find","latest","news","current","look up","what happened"],
        "calculator":   ["calculate","compute","solve","how much","math","+","-","*","/","percent","convert"],
        "code_execute": ["run","execute","output of","test this code","what does this code"],
        "wikipedia":    ["who is","what is","define","history of","explain what","biography"],
        "weather":      ["weather","temperature","forecast","rain","sunny","climate"],
        "file_read":    ["read file","open file","contents of","from file","in the file"],
        "datetime":     ["what time","current time","today's date","what day"],
    }

    def __init__(self, registry: ToolRegistry) -> None:
        self._reg = registry

    def select(self, prompt: str, max_tools: int = 3) -> List[str]:
        p = prompt.lower()
        scores: Dict[str, int] = {}
        for name, kws in self._KEYWORDS.items():
            if self._reg.get(name):
                s = sum(1 for kw in kws if kw in p)
                if s > 0: scores[name] = s
        return [n for n, _ in sorted(scores.items(), key=lambda x: -x[1])[:max_tools]]

    async def select_llm(self, prompt: str, loader, model: str, max_tools: int = 3) -> List[str]:
        instr = (f"{self._reg.schema_prompt()}\n\nQuery: {prompt}\n\n"
                 f"Which tools are needed? Reply ONLY as JSON array e.g. [\"web_search\"]\n"
                 f"Tools:")
        try:
            ans, _ = await loader.infer(model, instr, max_tokens=64, temperature=0.0)
            m = re.search(r'\[.*?\]', ans, re.DOTALL)
            if m:
                tools = json.loads(m.group())
                return [t for t in tools if self._reg.get(t)][:max_tools]
        except Exception as e:
            logger.warning("LLM tool select failed", error=str(e))
        return self.select(prompt, max_tools)
