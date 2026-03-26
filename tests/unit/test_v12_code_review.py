"""
SuperAI V12 — tests/unit/test_v12_code_review.py
Unit tests for Step 5: Code Review Engine
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCodeReviewEngine:

    def setup_method(self):
        from backend.code_review.code_review import CodeReviewEngine
        self.engine = CodeReviewEngine(model_loader=None)

    @pytest.mark.asyncio
    async def test_heuristic_review_clean_code(self):
        code = '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''
        result = await self.engine.review(code)
        assert result.total_issues == 0 or result.score > 0.5
        assert isinstance(result.summary, str)

    @pytest.mark.asyncio
    async def test_heuristic_review_detects_eval(self):
        code = 'result = eval(user_input)'
        result = await self.engine.review(code)
        assert result.critical > 0
        assert any(i.category == "security" for i in result.issues)

    @pytest.mark.asyncio
    async def test_heuristic_review_detects_long_lines(self):
        code = "x = " + "a" * 130
        result = await self.engine.review(code)
        assert any(i.category == "style" for i in result.issues)

    @pytest.mark.asyncio
    async def test_heuristic_review_detects_hardcoded_password(self):
        code = "password = 'supersecret123'"
        result = await self.engine.review(code)
        assert result.critical > 0

    @pytest.mark.asyncio
    async def test_heuristic_review_detects_todo(self):
        code = "x = 1  # TODO: fix this later"
        result = await self.engine.review(code)
        assert any("marker" in i.description.lower() or "todo" in i.description.lower()
                    for i in result.issues)

    @pytest.mark.asyncio
    async def test_review_result_structure(self):
        result = await self.engine.review("def f(): pass")
        assert hasattr(result, "total_issues")
        assert hasattr(result, "critical")
        assert hasattr(result, "warnings")
        assert hasattr(result, "info")
        assert hasattr(result, "score")
        assert hasattr(result, "summary")
        assert hasattr(result, "issues")

    @pytest.mark.asyncio
    async def test_suggest_fallback(self):
        code = "x = 1\ny = 2\nz = x + y"
        suggestions = await self.engine.suggest(code)
        assert len(suggestions) > 0
        assert all(isinstance(s, str) for s in suggestions)

    @pytest.mark.asyncio
    async def test_suggest_for_code_with_logging(self):
        code = '''
import logging
logger = logging.getLogger(__name__)

def process(data):
    """Process the data."""
    try:
        logger.info("Processing")
        return data * 2
    except Exception:
        logger.error("Failed")
'''
        suggestions = await self.engine.suggest(code)
        assert isinstance(suggestions, list)

    def test_parse_review_output(self):
        text = (
            "SEVERITY: critical\n"
            "CATEGORY: security\n"
            "LINE: 5\n"
            "ISSUE: SQL injection risk\n"
            "FIX: Use parameterized queries\n"
            "SCORE: 0.3\n"
            "SUMMARY: Security concerns found\n"
        )
        from backend.code_review.code_review import CodeReviewEngine
        result = CodeReviewEngine._parse_review(text, 20)
        assert result.critical == 1
        assert result.issues[0].category == "security"
        assert result.score == 0.3

    def test_parse_suggestions(self):
        text = "1. Add error handling\n2. Use type hints\n3. Add docstrings"
        from backend.code_review.code_review import CodeReviewEngine
        items = CodeReviewEngine._parse_suggestions(text)
        assert len(items) == 3
