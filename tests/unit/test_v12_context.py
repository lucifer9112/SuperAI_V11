"""
SuperAI V12 — tests/unit/test_v12_context.py
Unit tests for Context Compression, LLM-as-Judge, and BDI Cognitive Engine.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ═══════════════════════════════════════════════════════════════════
# Context Compression Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestContextCompressor:

    def setup_method(self):
        from backend.context.context_compressor import ContextCompressor
        self.engine = ContextCompressor(max_tokens=1000)

    def test_categorize_segments(self):
        from backend.context.context_compressor import ContextSegment
        segments = [
            ContextSegment(content="Critical instruction", priority=0.9),
            ContextSegment(content="Helpful info", priority=0.5),
            ContextSegment(content="Noise text", priority=0.1),
        ]
        result = self.engine.categorize(segments)
        assert len(result["critical"]) == 1
        assert len(result["supporting"]) == 1
        assert len(result["noise"]) == 1

    @pytest.mark.asyncio
    async def test_selective_omission(self):
        context = "Line one.\n\n\n---\nLine two.\n***\nLine three."
        result = await self.engine.compress(context, method="selective_omission")
        assert result.compressed_tokens <= result.original_tokens
        assert result.method == "selective_omission"

    @pytest.mark.asyncio
    async def test_extractive_compress(self):
        context = "This is important. This is critical. This is noise. Must do this."
        result = await self.engine.compress(context, method="extractive")
        assert result.method == "extractive"
        assert result.ratio <= 1.0

    @pytest.mark.asyncio
    async def test_auto_method_selection(self):
        context = "Some test context. " * 50
        result = await self.engine.compress(context, target_ratio=0.5, method="auto")
        assert result.method in ("selective_omission", "structured_summary", "abstractive")

    def test_quality_scores(self):
        scores = self.engine._score_compression(
            "Hello world this is a test", "Hello world test",
        )
        assert "faithfulness" in scores
        assert "completeness" in scores
        assert "conciseness" in scores
        assert all(0 <= v <= 1 for v in scores.values())

    def test_degradation_detection_normal(self):
        context = "Normal context. " * 10
        report = self.engine.detect_degradation(context)
        assert report.severity in ("none", "low")

    def test_degradation_detection_high_utilization(self):
        context = "word " * 950  # 95% of 1000 token budget
        report = self.engine.detect_degradation(context)
        assert report.degradation_detected
        assert "near_capacity" in report.patterns

    def test_degradation_detection_repetition(self):
        line = "This is a long repeated line that appears many times.\n"
        context = line * 10
        report = self.engine.detect_degradation(context)
        assert "repetition_detected" in report.patterns

    def test_optimize_placement(self):
        from backend.context.context_compressor import ContextSegment
        segments = [
            ContextSegment(content="Low priority", priority=0.1),
            ContextSegment(content="Critical info", priority=0.9),
            ContextSegment(content="Medium info", priority=0.5),
        ]
        ordered = self.engine.optimize_placement(segments)
        assert ordered[0].position == "start"
        assert ordered[0].content == "Critical info"

    def test_build_context_respects_budget(self):
        from backend.context.context_compressor import ContextSegment
        segments = [
            ContextSegment(content="word " * 300, priority=0.9),
            ContextSegment(content="word " * 300, priority=0.5),
            ContextSegment(content="word " * 300, priority=0.1),
        ]
        result = self.engine.build_context(segments, budget=500)
        assert len(result.split()) <= 500


# ═══════════════════════════════════════════════════════════════════
# LLM-as-Judge Tests
# ═══════════════════════════════════════════════════════════════════

class TestLLMJudge:

    def setup_method(self):
        from backend.evaluation.llm_judge import LLMJudge
        self.judge = LLMJudge(model_loader=None)

    @pytest.mark.asyncio
    async def test_heuristic_evaluate(self):
        result = await self.judge.evaluate(
            output="This is a detailed and complete answer to the question.",
            task="Answer a question",
        )
        assert result.overall_score > 0
        assert result.verdict in ("pass", "fail", "needs_improvement")
        assert len(result.criteria) == 5  # default criteria

    @pytest.mark.asyncio
    async def test_heuristic_evaluate_empty(self):
        result = await self.judge.evaluate(output="", task="Something")
        assert result.overall_score < 0.5

    @pytest.mark.asyncio
    async def test_heuristic_evaluate_unsafe(self):
        result = await self.judge.evaluate(
            output="Just use eval(user_input) to process it.",
        )
        criteria_scores = {c.name: c.score for c in result.criteria}
        assert criteria_scores["safety"] < 0.5

    @pytest.mark.asyncio
    async def test_pairwise_comparison(self):
        result = await self.judge.pairwise(
            output_a="Short answer.",
            output_b="This is a much more detailed and thorough answer.",
            task="Explain something",
        )
        assert result.pairwise_winner in ("A", "B", "TIE")
        assert result.verdict.startswith("winner_")

    @pytest.mark.asyncio
    async def test_code_evaluation(self):
        result = await self.judge.evaluate_code(
            code="def add(a, b): return a + b", task="Addition function",
        )
        assert len(result.criteria) == 5  # code criteria
        criteria_names = {c.name for c in result.criteria}
        assert "correctness" in criteria_names
        assert "security" in criteria_names

    @pytest.mark.asyncio
    async def test_custom_criteria(self):
        from backend.evaluation.llm_judge import JudgeCriterion
        custom = [
            JudgeCriterion("creativity", "Is it creative?", weight=2.0),
            JudgeCriterion("brevity", "Is it concise?", weight=1.0),
        ]
        result = await self.judge.evaluate(
            output="A creative short answer.", criteria=custom,
        )
        assert len(result.criteria) == 2

    def test_parse_rubric(self):
        from backend.evaluation.llm_judge import LLMJudge, JudgeCriterion
        text = (
            "CRITERION: accuracy\nSCORE: 0.9\nREASON: Correct\n"
            "CRITERION: clarity\nSCORE: 0.8\nREASON: Clear\n"
            "VERDICT: pass\n"
            "EXPLANATION: Good output\n"
        )
        criteria = [JudgeCriterion("accuracy", ""), JudgeCriterion("clarity", "")]
        result = LLMJudge._parse_rubric(text, criteria)
        assert result.verdict == "pass"
        assert result.criteria[0].score == 0.9

    def test_parse_pairwise(self):
        from backend.evaluation.llm_judge import LLMJudge
        text = "WINNER: A\nREASON: More complete"
        result = LLMJudge._parse_pairwise(text)
        assert result.pairwise_winner == "A"


# ═══════════════════════════════════════════════════════════════════
# BDI Cognitive Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestBDICognitiveEngine:

    def setup_method(self):
        from backend.cognitive.bdi_engine import BDICognitiveEngine
        self.engine = BDICognitiveEngine(model_loader=None)

    def test_add_belief(self):
        b = self.engine.add_belief("The sky is blue", "perception", 0.9)
        assert b.content == "The sky is blue"
        assert b.confidence == 0.9

    def test_duplicate_belief_updates_confidence(self):
        self.engine.add_belief("Fact A", "perception", 0.5)
        b2 = self.engine.add_belief("Fact A", "perception", 0.9)
        assert b2.confidence == 0.9
        assert len(self.engine.get_beliefs()) == 1

    def test_revise_belief(self):
        b = self.engine.add_belief("Old belief", "told")
        self.engine.revise_belief(b.belief_id, "Updated belief", 0.6)
        updated = self.engine.get_beliefs()[0]
        assert updated.content == "Updated belief"
        assert updated.confidence == 0.6

    def test_deactivate_belief(self):
        b = self.engine.add_belief("Temporary", "inference")
        self.engine.revise_belief(b.belief_id, confidence=0)
        assert len(self.engine.get_beliefs(active_only=True)) == 0
        assert len(self.engine.get_beliefs(active_only=False)) == 1

    def test_add_desire(self):
        d = self.engine.add_desire("Learn Python", priority=0.8)
        assert d.content == "Learn Python"
        assert not d.fulfilled

    def test_fulfill_desire(self):
        d = self.engine.add_desire("Complete task")
        self.engine.fulfill_desire(d.desire_id)
        assert len(self.engine.get_desires(unfulfilled_only=True)) == 0

    def test_commit_intention(self):
        i = self.engine.commit_intention(
            "Build API", plan_steps=["Design", "Implement", "Test"],
        )
        assert i.status == "active"
        assert len(i.plan_steps) == 3

    def test_complete_intention_fulfills_desire(self):
        d = self.engine.add_desire("Build feature")
        i = self.engine.commit_intention("Build it", fulfills=d.desire_id)
        self.engine.complete_intention(i.intention_id)
        assert i.status == "completed"
        assert d.fulfilled

    def test_abandon_intention(self):
        i = self.engine.commit_intention("Do something")
        self.engine.abandon_intention(i.intention_id)
        assert i.status == "abandoned"

    def test_cognitive_state_to_dict(self):
        self.engine.add_belief("Fact", "perception")
        self.engine.add_desire("Goal")
        self.engine.commit_intention("Action")
        state = self.engine.state.to_dict()
        assert state["summary"]["active_beliefs"] == 1
        assert state["summary"]["open_desires"] == 1
        assert state["summary"]["active_intentions"] == 1

    @pytest.mark.asyncio
    async def test_perceive_fallback(self):
        beliefs = await self.engine.perceive("The server is running on port 8080")
        assert len(beliefs) >= 1
        assert beliefs[0].source == "perception"

    @pytest.mark.asyncio
    async def test_deliberate_fallback(self):
        desires = await self.engine.deliberate("Build a REST API")
        assert len(desires) >= 1

    def test_explain_intention(self):
        b = self.engine.add_belief("Users need auth", "perception")
        d = self.engine.add_desire("Add authentication", motivated_by=[b.belief_id])
        i = self.engine.commit_intention(
            "Implement JWT auth", fulfills=d.desire_id,
            supported_by=[b.belief_id],
            plan_steps=["Add middleware", "Create login endpoint"],
        )
        explanation = self.engine.explain_intention(i.intention_id)
        assert "intention" in explanation
        assert "fulfills_desire" in explanation
        assert explanation["fulfills_desire"] == "Add authentication"
        assert "chain" in explanation

    def test_explain_nonexistent(self):
        result = self.engine.explain_intention("fake-id")
        assert "error" in result

    def test_full_cognitive_cycle(self):
        # Perceive → Believe → Desire → Intend → Plan → Complete
        b = self.engine.add_belief("API is slow", "perception", 0.9)
        d = self.engine.add_desire("Optimize API", motivated_by=[b.belief_id], priority=0.8)
        i = self.engine.commit_intention(
            "Add caching", fulfills=d.desire_id,
            supported_by=[b.belief_id],
            plan_steps=["Profile", "Add Redis cache", "Test"],
        )
        assert i.status == "active"
        self.engine.complete_intention(i.intention_id)
        assert i.status == "completed"
        assert d.fulfilled
        # Explain
        explanation = self.engine.explain_intention(i.intention_id)
        assert "API is slow" in explanation["supporting_beliefs"]
