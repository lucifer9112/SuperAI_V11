"""
SuperAI V12 — tests/unit/test_v12_debug.py
Unit tests for Step 5: Systematic Debugging Engine
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSystematicDebugger:

    def setup_method(self):
        from backend.debugging.debugger import SystematicDebugger
        self.debugger = SystematicDebugger(model_loader=None)

    @pytest.mark.asyncio
    async def test_full_debug_returns_report(self):
        report = await self.debugger.full_debug(
            error="TypeError: cannot add str and int",
            code="x = '5' + 3",
        )
        assert report.error_description
        assert len(report.phases) == 4
        assert report.root_cause
        assert report.proposed_fix
        assert report.verification_steps

    @pytest.mark.asyncio
    async def test_full_debug_phase_names(self):
        report = await self.debugger.full_debug(
            error="IndexError: list index out of range",
        )
        phase_names = [p.phase for p in report.phases]
        assert phase_names == ["reproduce", "isolate", "fix", "verify"]

    @pytest.mark.asyncio
    async def test_isolate_only(self):
        result = await self.debugger.isolate_only(
            error="KeyError: 'user_id'",
            code="data = {}; print(data['user_id'])",
        )
        assert result.phase == "isolate"
        assert result.analysis
        assert result.confidence >= 0.0

    @pytest.mark.asyncio
    async def test_report_to_dict(self):
        report = await self.debugger.full_debug(
            error="NullPointerException",
        )
        d = report.to_dict()
        assert "error_description" in d
        assert "root_cause" in d
        assert "proposed_fix" in d
        assert "verification_steps" in d
        assert "phases" in d
        assert len(d["phases"]) == 4

    @pytest.mark.asyncio
    async def test_overall_confidence(self):
        report = await self.debugger.full_debug(error="Some error")
        assert 0.0 <= report.overall_confidence <= 1.0

    @pytest.mark.asyncio
    async def test_verification_steps_not_empty(self):
        report = await self.debugger.full_debug(
            error="Connection refused on port 8080",
        )
        assert len(report.verification_steps) > 0


class TestDebugHelpers:

    def test_extract_root_cause(self):
        from backend.debugging.debugger import SystematicDebugger
        analysis = "Analysis here.\nMore details.\nRoot cause: missing null check on line 42."
        result = SystematicDebugger._extract_root_cause(analysis)
        assert len(result) > 10

    def test_extract_numbered_items(self):
        from backend.debugging.debugger import SystematicDebugger
        text = "1. Check logs\n2. Verify input\n3. Run tests"
        items = SystematicDebugger._extract_numbered_items(text)
        assert len(items) == 3
        assert "Check logs" in items[0]

    def test_extract_numbered_items_with_dashes(self):
        from backend.debugging.debugger import SystematicDebugger
        text = "- Step A\n- Step B"
        items = SystematicDebugger._extract_numbered_items(text)
        assert len(items) == 2

    def test_fallback_phase_reproduce(self):
        from backend.debugging.debugger import SystematicDebugger
        result = SystematicDebugger._fallback_phase("reproduce", "Some error")
        assert result.phase == "reproduce"
        assert result.analysis
        assert len(result.suggestions) > 0

    def test_fallback_phase_unknown(self):
        from backend.debugging.debugger import SystematicDebugger
        result = SystematicDebugger._fallback_phase("unknown_phase", "err")
        assert result.phase == "unknown_phase"
