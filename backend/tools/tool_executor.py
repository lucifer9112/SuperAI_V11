"""
SuperAI V11 — backend/tools/tool_executor.py
STEP 2: Tool Calling Engine — Built-in Tools + Sandboxed Executor

Built-in tools: web_search, calculator, code_execute, wikipedia, weather, file_read, datetime
Security: code_execute uses subprocess with 10s timeout + blocked dangerous imports
"""
from __future__ import annotations
import asyncio, ast, math, os, re, subprocess, sys, tempfile, time, urllib.parse, urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger
from backend.tools.tool_registry import ToolDef, ToolRegistry, ToolResult

MAX_OUT = 2000  # chars
BLOCKED_MODULES = {"builtins", "os", "sys", "subprocess", "socket", "requests", "importlib", "pathlib"}
BLOCKED_CALLS = {"__import__", "open", "exec", "eval", "compile", "input",
                 "getattr", "setattr", "delattr", "globals", "locals", "vars"}
BLOCKED_NAMES = {"__builtins__", "__loader__", "__spec__", "__package__", "__cached__", "__file__"}


def _call_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _validate_python_code(code: str) -> Optional[str]:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return f"Syntax error: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id in BLOCKED_NAMES:
                return f"Blocked name: {node.id}"
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                return f"Blocked attribute: {node.attr}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_MODULES:
                    return f"Blocked import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BLOCKED_MODULES:
                return f"Blocked import: {node.module}"
        elif isinstance(node, ast.Call):
            name = _call_name(node.func) or ""
            root = name.split(".")[0]
            if name in BLOCKED_CALLS or root in BLOCKED_CALLS:
                return f"Blocked call: {name}"
            if name.endswith("import_module") and root == "importlib":
                return "Blocked call: importlib.import_module"
    return None


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, monitoring=None) -> None:
        self._reg = registry
        self._monitoring = monitoring

    @property
    def MAX_OUT(self) -> int:  # pragma: no cover - compatibility shim
        return MAX_OUT

    async def execute(self, name: str, args: Dict[str, Any]) -> ToolResult:
        tool = self._reg.get(name)
        if not tool:
            if self._monitoring:
                self._monitoring.record_tool(name, False)
                self._monitoring.record_error("tool_not_found")
            return ToolResult(name, False, "", error=f"Tool '{name}' not found")
        t0 = time.perf_counter()
        try:
            out = await asyncio.wait_for(tool.handler(**args), timeout=tool.timeout_s)
            ms  = (time.perf_counter()-t0)*1000
            out = str(out)
            if len(out) > MAX_OUT: out = out[:MAX_OUT] + "... [truncated]"
            if self._monitoring:
                self._monitoring.record_tool(name, True)
            return ToolResult(name, True, out, exec_ms=round(ms,1))
        except asyncio.TimeoutError:
            if self._monitoring:
                self._monitoring.record_tool(name, False)
                self._monitoring.record_error("tool_timeout")
            return ToolResult(name, False, "", error=f"Timeout after {tool.timeout_s}s",
                              exec_ms=(time.perf_counter()-t0)*1000)
        except Exception as e:
            logger.warning("Tool failed", tool=name, error=str(e))
            if self._monitoring:
                self._monitoring.record_tool(name, False)
                self._monitoring.record_error("tool_error")
            return ToolResult(name, False, "", error=str(e)[:200],
                              exec_ms=(time.perf_counter()-t0)*1000)

    async def execute_many(self, calls: List[Dict]) -> List[ToolResult]:
        return await asyncio.gather(*[
            self.execute(c["name"], c.get("arguments", {})) for c in calls
        ])


# ── Built-in tool handlers ────────────────────────────────────────

async def _web_search(query: str, max_results: int = 5) -> str:
    def _run():
        from duckduckgo_search import DDGS
        with DDGS() as d:
            results = list(d.text(query, max_results=max_results))
        if not results: return "No results found."
        return "\n\n".join(
            f"**{r.get('title','')}**\n{r.get('body','')[:300]}\nURL: {r.get('href','')}"
            for r in results)
    return await asyncio.to_thread(_run)


async def _calculator(expression: str) -> str:
    expr = expression.strip().replace("^","**").replace("x","*").replace("×","*").replace("÷","/")
    safe = {"sqrt":math.sqrt,"sin":math.sin,"cos":math.cos,"tan":math.tan,
            "log":math.log,"log10":math.log10,"abs":abs,"round":round,
            "floor":math.floor,"ceil":math.ceil,"pi":math.pi,"e":math.e}
    try:
        tree = ast.parse(expr, mode="eval")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if not (isinstance(node.func, ast.Name) and node.func.id in safe):
                    return f"Unsafe function in expression"
        result = eval(compile(tree,"<str>","eval"), {"__builtins__": {}}, safe)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Calculation error: {e}"


async def _code_execute(code: str, language: str = "python") -> str:
    if language.lower() != "python":
        return f"Only Python supported. Got: {language}"
    blocked = _validate_python_code(code)
    if blocked:
        return blocked
    def _run():
        with tempfile.TemporaryDirectory(prefix="superai_tool_") as temp_dir:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONNOUSERSITE"] = "1"
            r = subprocess.run(
                [sys.executable, "-I", "-c", code],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=temp_dir,
                env=env,
            )
        out, err = r.stdout or "", r.stderr or ""
        if err: return f"Output:\n{out}\nErrors:\n{err}" if out else f"Error:\n{err}"
        return out or "(No output)"
    try:    return await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired: return "Timeout (10s limit)"


async def _wikipedia(topic: str, sentences: int = 3) -> str:
    def _run():
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(topic)}"
            req = urllib.request.Request(url, headers={"User-Agent": "SuperAI-V12/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                import json as _j
                data = _j.loads(r.read())
            extract = data.get("extract","")
            sents   = re.split(r'(?<=[.!?])\s+', extract)
            return " ".join(sents[:sentences])
        except Exception as e:
            return f"Wikipedia error: {e}"
    return await asyncio.to_thread(_run)


async def _weather(city: str) -> str:
    def _run():
        url = f"https://wttr.in/{city.replace(' ','+')}?format=3"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SuperAI-V12/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return r.read().decode()
        except Exception as e:
            return f"Weather error: {e}"
    return await asyncio.to_thread(_run)


async def _file_read(filename: str) -> str:
    safe_dir = (Path(__file__).resolve().parents[2] / "data" / "uploads").resolve()
    target = (safe_dir / Path(filename).name).resolve()
    if not target.is_relative_to(safe_dir):
        return "Access denied."
    if not target.exists(): return f"File not found: {filename}"
    try:
        txt = target.read_text(errors="replace")
        return txt[:2000] + ("... [truncated]" if len(txt)>2000 else "")
    except Exception as e:
        return f"Read error: {e}"


async def _datetime_now() -> str:
    from datetime import datetime, timezone
    return f"Current UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"


def create_tool_registry() -> ToolRegistry:
    """Factory — returns fully populated registry."""
    reg = ToolRegistry()
    tools = [
        ToolDef("web_search","Search the internet for current information, news, or facts.",
            {"type":"object","properties":{"query":{"type":"string","description":"Search query"},
             "max_results":{"type":"integer"}},"required":["query"]},
            _web_search, "search", timeout_s=15),
        ToolDef("calculator","Evaluate a math expression. Supports +,-,*,/,**,sqrt,sin,cos,log.",
            {"type":"object","properties":{"expression":{"type":"string"}},"required":["expression"]},
            _calculator, "math", timeout_s=5),
        ToolDef("code_execute","Execute Python code safely and return output.",
            {"type":"object","properties":{"code":{"type":"string"},
             "language":{"type":"string"}},"required":["code"]},
            _code_execute, "code", safe=False, timeout_s=12),
        ToolDef("wikipedia","Get a Wikipedia summary for a person, place, or concept.",
            {"type":"object","properties":{"topic":{"type":"string"},
             "sentences":{"type":"integer"}},"required":["topic"]},
            _wikipedia, "search", timeout_s=12),
        ToolDef("weather","Get current weather for a city.",
            {"type":"object","properties":{"city":{"type":"string"}},"required":["city"]},
            _weather, "general", timeout_s=10),
        ToolDef("file_read","Read a file from the uploads directory.",
            {"type":"object","properties":{"filename":{"type":"string"}},"required":["filename"]},
            _file_read, "file", timeout_s=5),
        ToolDef("datetime","Get current date and time in UTC.",
            {"type":"object","properties":{},"required":[]},
            _datetime_now, "general", timeout_s=2),
    ]
    for t in tools: reg.register(t)
    logger.info("Tool registry created", tools=len(reg))
    return reg
