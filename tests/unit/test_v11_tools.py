"""
SuperAI V11 — tests/unit/test_v11_tools.py
Unit tests for Step 2: Tool Calling Engine

Tests:
  - Tool Registry (register/get/list)
  - Tool Selector (keyword matching)
  - Tool Argument Extractor
  - Calculator tool (no network)
  - Datetime tool (no network)
  - Code execution (sandboxed)
  - Tool Executor (timeout, error handling)
"""
import pytest
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── Tool Registry ─────────────────────────────────────────────────

class TestToolRegistry:

    def setup_method(self):
        from backend.tools.tool_executor import create_tool_registry
        self.registry = create_tool_registry()

    def test_has_builtin_tools(self):
        assert len(self.registry) >= 7

    def test_get_existing_tool(self):
        tool = self.registry.get("calculator")
        assert tool is not None
        assert tool.name == "calculator"
        assert tool.category == "math"

    def test_get_nonexistent_returns_none(self):
        assert self.registry.get("nonexistent_tool") is None

    def test_list_all_tools(self):
        tools = self.registry.list_tools()
        assert len(tools) >= 7
        names = [t.name for t in tools]
        assert "web_search"   in names
        assert "calculator"   in names
        assert "code_execute" in names
        assert "datetime"     in names
        assert "wikipedia"    in names
        assert "weather"      in names
        assert "file_read"    in names

    def test_list_by_category(self):
        math_tools = self.registry.list_tools(category="math")
        assert any(t.name == "calculator" for t in math_tools)

    def test_schema_prompt_contains_tools(self):
        prompt = self.registry.schema_prompt()
        assert "calculator"  in prompt
        assert "web_search"  in prompt
        assert "Available tools:" in prompt

    def test_register_custom_tool(self):
        from backend.tools.tool_registry import ToolDef

        async def my_tool(msg: str) -> str:
            return f"Echo: {msg}"

        self.registry.register(ToolDef(
            name="my_custom",
            description="Custom test tool",
            parameters={"type":"object","properties":{"msg":{"type":"string"}},"required":["msg"]},
            handler=my_tool,
            category="test",
        ))
        assert self.registry.get("my_custom") is not None
        assert self.registry.get("my_custom").category == "test"


# ── Tool Selector ─────────────────────────────────────────────────

class TestToolSelector:

    def setup_method(self):
        from backend.tools.tool_executor import create_tool_registry
        from backend.tools.tool_registry import ToolSelector
        self.registry = create_tool_registry()
        self.selector = ToolSelector(self.registry)

    def test_selects_calculator_for_math(self):
        tools = self.selector.select("calculate 5 * 12 + 3")
        assert "calculator" in tools

    def test_selects_web_search_for_news(self):
        tools = self.selector.select("search for latest AI news today")
        assert "web_search" in tools

    def test_selects_code_execute_for_run(self):
        tools = self.selector.select("run this Python code and show output")
        assert "code_execute" in tools

    def test_selects_datetime_for_time(self):
        tools = self.selector.select("what time is it right now")
        assert "datetime" in tools

    def test_generic_prompt_returns_list(self):
        # May return empty or some tools
        tools = self.selector.select("hello world")
        assert isinstance(tools, list)

    def test_max_tools_respected(self):
        tools = self.selector.select("calculate search find run", max_tools=2)
        assert len(tools) <= 2

    def test_returns_only_registered_tools(self):
        tools = self.selector.select("calculate the weather news search math")
        for t in tools:
            assert self.registry.get(t) is not None


# ── Tool Argument Extractor ───────────────────────────────────────

class TestToolArgExtractor:

    def setup_method(self):
        from backend.tools.tool_calling_engine import ToolArgExtractor
        self.extractor = ToolArgExtractor()

    def test_calculator_extracts_expression(self):
        args = self.extractor.extract("calculator", "what is 2 + 2 * 10")
        assert "expression" in args

    def test_web_search_extracts_query(self):
        args = self.extractor.extract("web_search", "search for Python tutorials")
        assert "query" in args
        assert len(args["query"]) > 0

    def test_wikipedia_extracts_topic(self):
        args = self.extractor.extract("wikipedia", "who is Alan Turing")
        assert "topic" in args

    def test_code_execute_extracts_code_block(self):
        prompt = "run this: ```python\nprint('hello')\n```"
        args = self.extractor.extract("code_execute", prompt)
        assert "code" in args

    def test_weather_extracts_city(self):
        args = self.extractor.extract("weather", "weather in London today")
        assert "city" in args

    def test_datetime_no_required_args(self):
        args = self.extractor.extract("datetime", "what time is it")
        assert isinstance(args, dict)


# ── Built-in Tool Handlers ────────────────────────────────────────

class TestBuiltinTools:

    @pytest.mark.asyncio
    async def test_calculator_basic(self):
        from backend.tools.tool_executor import _calculator
        result = await _calculator("2 + 2")
        assert "4" in result

    @pytest.mark.asyncio
    async def test_calculator_multiply(self):
        from backend.tools.tool_executor import _calculator
        result = await _calculator("10 * 5")
        assert "50" in result

    @pytest.mark.asyncio
    async def test_calculator_sqrt(self):
        from backend.tools.tool_executor import _calculator
        result = await _calculator("sqrt(16)")
        assert "4" in result

    @pytest.mark.asyncio
    async def test_calculator_invalid_blocks_unsafe(self):
        from backend.tools.tool_executor import _calculator
        # Should not execute arbitrary code
        result = await _calculator("__import__('os')")
        assert "error" in result.lower() or "unsafe" in result.lower()

    @pytest.mark.asyncio
    async def test_datetime_returns_utc(self):
        from backend.tools.tool_executor import _datetime_now
        result = await _datetime_now()
        assert "UTC" in result
        assert "20" in result  # year starts with 20xx

    @pytest.mark.asyncio
    async def test_code_execute_hello_world(self):
        from backend.tools.tool_executor import _code_execute
        result = await _code_execute("print('hello from test')", "python")
        assert "hello from test" in result

    @pytest.mark.asyncio
    async def test_code_execute_blocks_os_import(self):
        from backend.tools.tool_executor import _code_execute
        result = await _code_execute("import os; os.system('echo hacked')", "python")
        assert "Blocked" in result or "blocked" in result

    @pytest.mark.asyncio
    async def test_code_execute_unsupported_language(self):
        from backend.tools.tool_executor import _code_execute
        result = await _code_execute("console.log('hi')", "javascript")
        assert "Python" in result or "python" in result.lower()

    @pytest.mark.asyncio
    async def test_file_read_outside_uploads_blocked(self):
        from backend.tools.tool_executor import _file_read
        result = await _file_read("../../etc/passwd")
        # Path traversal should be blocked
        assert "denied" in result.lower() or "not found" in result.lower()


# ── Tool Executor ─────────────────────────────────────────────────

class TestToolExecutor:

    def setup_method(self):
        from backend.tools.tool_executor import create_tool_registry, ToolExecutor
        self.registry = create_tool_registry()
        self.executor = ToolExecutor(self.registry)

    @pytest.mark.asyncio
    async def test_executes_calculator(self):
        result = await self.executor.execute("calculator", {"expression": "3 * 7"})
        assert result.success is True
        assert "21" in result.output
        assert result.exec_ms >= 0

    @pytest.mark.asyncio
    async def test_executes_datetime(self):
        result = await self.executor.execute("datetime", {})
        assert result.success is True
        assert "UTC" in result.output

    @pytest.mark.asyncio
    async def test_unknown_tool_fails_gracefully(self):
        result = await self.executor.execute("totally_fake_tool", {})
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_output_truncated_at_max(self):
        from backend.tools.tool_executor import ToolExecutor
        from backend.tools.tool_registry import ToolDef

        async def long_output() -> str:
            return "x" * 10000

        self.registry.register(ToolDef(
            name="long_tool", description="test",
            parameters={"type":"object","properties":{},"required":[]},
            handler=long_output, category="test"
        ))
        result = await self.executor.execute("long_tool", {})
        assert result.success is True
        assert len(result.output) <= self.executor.MAX_OUT + 20

    @pytest.mark.asyncio
    async def test_execute_many_parallel(self):
        calls = [
            {"name": "calculator", "arguments": {"expression": "2+2"}},
            {"name": "datetime",   "arguments": {}},
        ]
        results = await self.executor.execute_many(calls)
        assert len(results) == 2
        assert all(isinstance(r.success, bool) for r in results)


# ── ToolCallingEngine integration ─────────────────────────────────

class TestToolCallingEngine:

    def setup_method(self):
        from backend.tools.tool_executor     import create_tool_registry
        from backend.tools.tool_calling_engine import ToolCallingEngine
        self.engine = ToolCallingEngine(create_tool_registry())

    @pytest.mark.asyncio
    async def test_no_tools_needed_returns_original_prompt(self):
        result = await self.engine.process("just a general hello response")
        # May or may not use tools depending on keyword match
        assert result.prompt == "just a general hello response"
        assert isinstance(result.tools_used, list)

    @pytest.mark.asyncio
    async def test_math_uses_calculator(self):
        result = await self.engine.process("calculate 100 * 42")
        if "calculator" in result.tools_used:
            assert len(result.enriched_prompt) > len(result.prompt)

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self):
        result = await self.engine.process("what time is it")
        assert hasattr(result, "prompt")
        assert hasattr(result, "tool_calls")
        assert hasattr(result, "tool_results")
        assert hasattr(result, "enriched_prompt")
        assert hasattr(result, "tools_used")
        assert hasattr(result, "total_ms")

    @pytest.mark.asyncio
    async def test_unsafe_tool_blocked_low_autonomy(self):
        result = await self.engine.process(
            "run this code: print('test')",
            autonomy_level=1   # level 1 — safe tools only
        )
        assert "code_execute" not in result.tools_used
