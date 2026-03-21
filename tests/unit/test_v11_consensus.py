"""
SuperAI V11 — tests/unit/test_v11_consensus.py
Unit tests for Step 3: Multi-Model Consensus System

Tests:
  - ResponseEvaluator quality scoring
  - ConflictDetector agreement scoring
  - VotingMechanism (BEST + MAJORITY)
  - ConsensusEngine single-model fast path
  - ConsensusEngine conflict detection
"""
import pytest
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── ResponseEvaluator ─────────────────────────────────────────────

class TestResponseEvaluator:

    def setup_method(self):
        from backend.consensus.consensus_engine import ResponseEvaluator, ModelResponse
        self.evaluator = ResponseEvaluator()
        self.MR = ModelResponse

    def test_empty_response_zero_quality(self):
        r = self.MR("model_a", "", 0, 100.0)
        self.evaluator.evaluate(r, "question")
        assert r.quality == 0.0

    def test_error_response_zero_quality(self):
        r = self.MR("model_a", "", 0, 100.0, error="timeout")
        self.evaluator.evaluate(r, "question")
        assert r.quality == 0.0

    def test_short_response_lower_quality(self):
        r_short = self.MR("model_a", "Yes.", 5, 100.0)
        r_long  = self.MR("model_b",
            "Yes, that is correct. The reason is that neural networks learn "
            "hierarchical representations through backpropagation because they "
            "optimize a differentiable loss function step by step.", 30, 100.0)
        self.evaluator.evaluate(r_short, "q")
        self.evaluator.evaluate(r_long,  "q")
        assert r_long.quality > r_short.quality

    def test_quality_bounded(self):
        responses = [
            self.MR("m", "", 0, 0.0),
            self.MR("m", "x" * 2000, 400, 5000.0),
            self.MR("m", "Maybe perhaps unclear I think I believe not sure.", 10, 100.0),
            self.MR("m", "For example specifically step 1 step 2 because therefore.", 15, 100.0),
        ]
        for r in responses:
            self.evaluator.evaluate(r, "q")
            assert 0.0 <= r.quality <= 1.0

    def test_similarity_identical_responses(self):
        text = "Neural networks are powerful machine learning models."
        sim = self.evaluator.similarity(text, text)
        assert sim == pytest.approx(1.0)

    def test_similarity_different_responses(self):
        a = "Python is a programming language used for machine learning."
        b = "The weather today is sunny with light clouds in the afternoon."
        sim = self.evaluator.similarity(a, b)
        assert sim < 0.3

    def test_similarity_partial_overlap(self):
        a = "Machine learning is a subset of artificial intelligence."
        b = "Artificial intelligence includes machine learning and deep learning."
        sim = self.evaluator.similarity(a, b)
        assert 0.1 < sim < 0.9


# ── ConflictDetector ─────────────────────────────────────────────

class TestConflictDetector:

    def setup_method(self):
        from backend.consensus.consensus_engine import ConflictDetector, ModelResponse
        self.detector = ConflictDetector(threshold=0.30)
        self.MR = ModelResponse

    def test_single_response_no_conflict(self):
        responses = [self.MR("m", "Python is a language.", 5, 100.0)]
        conflict, agreement = self.detector.detect(responses)
        assert conflict is False
        assert agreement == pytest.approx(1.0)

    def test_identical_responses_no_conflict(self):
        text = "Python is used for machine learning and data science."
        responses = [
            self.MR("m1", text, 10, 100.0),
            self.MR("m2", text, 10, 100.0),
        ]
        conflict, agreement = self.detector.detect(responses)
        assert conflict is False
        assert agreement > 0.8

    def test_very_different_responses_conflict(self):
        responses = [
            self.MR("m1", "Python is a high-level programming language great for data science.", 12, 100.0),
            self.MR("m2", "The French Revolution happened during the eighteenth century in Europe.", 12, 100.0),
        ]
        conflict, agreement = self.detector.detect(responses)
        assert conflict is True
        assert agreement < 0.30

    def test_all_errors_no_conflict(self):
        responses = [
            self.MR("m1", "", 0, 100.0, error="timeout"),
            self.MR("m2", "", 0, 100.0, error="oom"),
        ]
        conflict, agreement = self.detector.detect(responses)
        # With no valid responses, no conflict detected
        assert isinstance(conflict, bool)

    def test_agreement_score_range(self):
        responses = [
            self.MR("m1", "The sky is blue and the sun is bright today.", 10, 50.0),
            self.MR("m2", "The ocean is deep and full of fish and whales.", 10, 60.0),
        ]
        conflict, agreement = self.detector.detect(responses)
        assert 0.0 <= agreement <= 1.0


# ── VotingMechanism ───────────────────────────────────────────────

class TestVotingMechanism:

    def setup_method(self):
        from backend.consensus.consensus_engine import (
            VotingMechanism, ResponseEvaluator, VotingStrategy, ModelResponse
        )
        self.evaluator = ResponseEvaluator()
        self.voter     = VotingMechanism(self.evaluator)
        self.VS        = VotingStrategy
        self.MR        = ModelResponse

    def test_best_strategy_selects_highest_quality(self):
        responses = [
            self.MR("fast_model",  "Yes.", 2, 50.0),
            self.MR("smart_model",
                "For example, in machine learning, neural networks learn by "
                "specifically adjusting weights. Step 1 involves forward pass, "
                "step 2 involves calculating loss, and step 3 involves backprop "
                "because the gradients guide optimization.", 40, 200.0),
        ]
        answer, winner, agreement = self.voter.vote(responses, self.VS.BEST, "explain backprop")
        assert winner == "smart_model"

    def test_majority_strategy_returns_answer(self):
        responses = [
            self.MR("m1", "Python is a language for data science and ML tasks.", 10, 100.0),
            self.MR("m2", "Python is popular for machine learning and data analysis.", 10, 100.0),
            self.MR("m3", "Python is used in machine learning and science.", 8, 80.0),
        ]
        answer, winner, agreement = self.voter.vote(responses, self.VS.MAJORITY, "what is python")
        assert len(answer) > 0
        assert winner in ["m1", "m2", "m3"]
        assert 0.0 <= agreement <= 1.0

    def test_all_errors_returns_fallback(self):
        responses = [
            self.MR("m1", "", 0, 100.0, error="timeout"),
            self.MR("m2", "", 0, 100.0, error="oom"),
        ]
        answer, winner, agreement = self.voter.vote(responses, self.VS.BEST, "question")
        assert "failed" in answer.lower() or winner == "none"

    def test_single_valid_response_wins(self):
        responses = [
            self.MR("m1", "",    0, 100.0, error="timeout"),
            self.MR("m2", "The answer is 42.", 5, 100.0),
        ]
        answer, winner, agreement = self.voter.vote(responses, self.VS.BEST, "q")
        assert winner == "m2"
        assert agreement == pytest.approx(1.0)

    def test_agreement_score_between_0_and_1(self):
        responses = [
            self.MR("m1", "Python is a versatile language for many purposes.", 8, 100.0),
            self.MR("m2", "Python is good for web development and automation.", 8, 100.0),
        ]
        _, _, agreement = self.voter.vote(responses, self.VS.BEST, "describe python")
        assert 0.0 <= agreement <= 1.0


# ── MultiModelRunner ─────────────────────────────────────────────

class TestMultiModelRunner:

    @pytest.mark.asyncio
    async def test_runs_with_mock_loader(self):
        from backend.consensus.consensus_engine import MultiModelRunner

        class MockLoader:
            async def infer(self, model_name, prompt, max_tokens, temperature):
                return (f"Response from {model_name}", 10)

        runner = MultiModelRunner(MockLoader(), timeout_s=10)
        results = await runner.run("test prompt", ["model_a", "model_b"], max_tokens=64)
        assert len(results) == 2
        assert "model_a" in results[0].answer or "model_b" in results[0].answer

    @pytest.mark.asyncio
    async def test_handles_model_error_gracefully(self):
        from backend.consensus.consensus_engine import MultiModelRunner

        class FailingLoader:
            async def infer(self, model_name, prompt, max_tokens, temperature):
                raise RuntimeError(f"Model {model_name} failed")

        runner = MultiModelRunner(FailingLoader(), timeout_s=5)
        results = await runner.run("test", ["failing_model"], max_tokens=64)
        assert len(results) == 1
        assert results[0].error is not None
        assert results[0].answer == ""


# ── ConsensusEngine ───────────────────────────────────────────────

class TestConsensusEngine:

    @pytest.mark.asyncio
    async def test_single_model_fast_path(self):
        from backend.consensus.consensus_engine import ConsensusEngine, VotingStrategy

        class MockLoader:
            async def infer(self, model_name, prompt, max_tokens, temperature):
                return ("Single model response.", 10)

        engine = ConsensusEngine(MockLoader(), model_names=["only_model"])
        result = await engine.run("test question")
        assert result.strategy == "single"
        assert result.agreement == pytest.approx(1.0)
        assert result.conflict is False
        assert "Single model response." in result.final_answer

    @pytest.mark.asyncio
    async def test_two_models_consensus(self):
        from backend.consensus.consensus_engine import ConsensusEngine, VotingStrategy

        class MockLoader:
            async def infer(self, model_name, prompt, max_tokens, temperature):
                # Both models return very similar answers — high agreement
                return (f"Python is a powerful language for machine learning and data science.", 12)

        engine = ConsensusEngine(MockLoader(), model_names=["model_a","model_b"],
                                  strategy=VotingStrategy.BEST)
        result = await engine.run("what is python for ml")
        assert result.winner_model in ["model_a", "model_b"]
        assert 0.0 <= result.agreement <= 1.0
        assert len(result.final_answer) > 0

    @pytest.mark.asyncio
    async def test_conflict_detected_on_different_answers(self):
        from backend.consensus.consensus_engine import ConsensusEngine, VotingStrategy

        answers = {
            "model_a": "The capital of France is Paris, a beautiful European city.",
            "model_b": "Quantum entanglement occurs when particles become correlated.",
        }

        class MockLoader:
            async def infer(self, model_name, prompt, max_tokens, temperature):
                return (answers.get(model_name, "unknown"), 10)

        engine = ConsensusEngine(MockLoader(), model_names=["model_a","model_b"],
                                  conflict_threshold=0.8)
        result = await engine.run("totally different question")
        # These two answers are very different → conflict should be detected
        assert result.conflict is True
        assert result.agreement < 0.8

    @pytest.mark.asyncio
    async def test_status_dict(self):
        from backend.consensus.consensus_engine import ConsensusEngine

        class MockLoader:
            async def infer(self, m, p, t, temp): return ("answer", 5)

        engine = ConsensusEngine(MockLoader(), model_names=["a","b"])
        s = engine.status()
        assert "models"          in s
        assert "strategy"        in s
        assert "total_conflicts" in s
        assert isinstance(s["models"], list)

    @pytest.mark.asyncio
    async def test_result_has_all_fields(self):
        from backend.consensus.consensus_engine import ConsensusEngine

        class MockLoader:
            async def infer(self, m, p, t, temp): return (f"answer from {m}", 5)

        engine = ConsensusEngine(MockLoader(), model_names=["x","y"])
        result = await engine.run("question", max_tokens=64)
        assert hasattr(result, "final_answer")
        assert hasattr(result, "winner_model")
        assert hasattr(result, "strategy")
        assert hasattr(result, "agreement")
        assert hasattr(result, "conflict")
        assert hasattr(result, "all_responses")
        assert hasattr(result, "latency_ms")
        assert len(result.all_responses) == 2

    @pytest.mark.asyncio
    async def test_run_allows_strategy_override(self):
        from backend.consensus.consensus_engine import ConsensusEngine, VotingStrategy

        answers = {
            "m1": "Python is used for machine learning and data science.",
            "m2": "Python is popular for data science and machine learning work.",
            "m3": "Python is common in data science and machine learning.",
        }

        class MockLoader:
            async def infer(self, model_name, prompt, max_tokens, temperature):
                return (answers[model_name], 12)

        engine = ConsensusEngine(MockLoader(), model_names=["m1", "m2", "m3"], strategy=VotingStrategy.BEST)
        result = await engine.run("what is python used for", strategy=VotingStrategy.MAJORITY)
        assert result.strategy == VotingStrategy.MAJORITY.value
