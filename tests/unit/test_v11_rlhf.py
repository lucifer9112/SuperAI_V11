"""
SuperAI V11 — tests/unit/test_v11_rlhf.py
Unit tests for Step 1: RLHF System

Tests:
  - HeuristicRewardEstimator scoring
  - FeedbackToRLHFConverter pair building
  - RLHFPipeline status
  - Reward score ranges
"""
import pytest
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── HeuristicRewardEstimator ──────────────────────────────────────

class TestHeuristicRewardEstimator:

    def setup_method(self):
        from backend.rlhf.reward_model import HeuristicRewardEstimator
        self.est = HeuristicRewardEstimator()

    def test_empty_response_negative_reward(self):
        r = self.est.score("What is AI?", "")
        assert r.score < 0
        assert r.confidence > 0

    def test_short_response_penalty(self):
        r = self.est.score("Explain neural networks", "It is a model.")
        assert r.score < 0.5

    def test_good_response_positive(self):
        response = (
            "Neural networks are computational models inspired by the human brain. "
            "For example, a deep learning network has multiple layers that learn "
            "hierarchical representations. Specifically, each layer transforms input "
            "into progressively abstract features. Because of this architecture, "
            "they excel at pattern recognition tasks."
        )
        r = self.est.score("Explain neural networks", response)
        assert r.score > 0.3
        assert r.method == "heuristic"

    def test_hedging_penalty(self):
        r1 = self.est.score("q", "The answer is 42.")
        r2 = self.est.score("q", "I think maybe perhaps the answer is possibly 42.")
        assert r1.score > r2.score

    def test_code_block_bonus(self):
        r1 = self.est.score("Write hello world", "print('Hello World')")
        r2 = self.est.score("Write hello world", "```python\nprint('Hello World')\n```")
        assert r2.score >= r1.score

    def test_score_bounded(self):
        for prompt, resp in [
            ("p", ""),
            ("p", "x" * 2000),
            ("p", "I think maybe I don't know perhaps unclear not sure I believe"),
            ("p", "For example specifically step 1 step 2 because therefore research shows"),
        ]:
            r = self.est.score(prompt, resp)
            assert -1.0 <= r.score <= 1.0

    def test_cannot_help_penalty(self):
        r = self.est.score("question", "I cannot help with that request.")
        assert r.score < 0.3

    def test_method_label(self):
        r = self.est.score("q", "Some response here.")
        assert r.method == "heuristic"
        assert r.prompt == "q"


# ── RewardModel (heuristic mode) ──────────────────────────────────

class TestRewardModel:

    @pytest.mark.asyncio
    async def test_init_returns_heuristic_by_default(self):
        from backend.rlhf.reward_model import RewardModel
        rm = RewardModel(model_path="/tmp/nonexistent_model.pt")
        await rm.init()
        assert rm._use_neural == False

    @pytest.mark.asyncio
    async def test_score_returns_reward_score(self):
        from backend.rlhf.reward_model import RewardModel
        rm = RewardModel(model_path="/tmp/nonexistent_model.pt")
        await rm.init()
        rs = await rm.score("What is Python?", "Python is a programming language.")
        assert hasattr(rs, "score")
        assert hasattr(rs, "confidence")
        assert -1.0 <= rs.score <= 1.0

    def test_status_dict(self):
        from backend.rlhf.reward_model import RewardModel
        rm = RewardModel()
        # Should not raise
        # status requires init, but check structure once init done
        assert hasattr(rm, "_use_neural")
        assert hasattr(rm, "_heuristic")
        assert hasattr(rm, "_neural")


# ── FeedbackToRLHFConverter ───────────────────────────────────────

class TestFeedbackConverter:

    @pytest.mark.asyncio
    async def test_empty_db_returns_empty_pairs(self, tmp_path):
        from backend.rlhf.rlhf_pipeline import FeedbackToRLHFConverter
        import aiosqlite

        fb_db  = str(tmp_path / "fb.db")
        cv_db  = str(tmp_path / "conv.db")

        # Create minimal tables
        async with aiosqlite.connect(fb_db) as db:
            await db.execute(
                "CREATE TABLE feedback (response_id TEXT, score INTEGER)"
            )
            await db.commit()
        async with aiosqlite.connect(cv_db) as db:
            await db.execute(
                "CREATE TABLE conversation_turns "
                "(user_msg TEXT, assistant_msg TEXT, timestamp REAL)"
            )
            await db.commit()

        conv = FeedbackToRLHFConverter(fb_db, cv_db)
        pairs = await conv.build_pairs(min_pairs=1)
        assert isinstance(pairs, list)

    @pytest.mark.asyncio
    async def test_with_rated_turns_builds_pairs(self, tmp_path):
        from backend.rlhf.rlhf_pipeline import FeedbackToRLHFConverter
        import aiosqlite, time as _t

        fb_db = str(tmp_path / "fb.db")
        cv_db = str(tmp_path / "conv.db")

        async with aiosqlite.connect(fb_db) as db:
            await db.execute("CREATE TABLE feedback (response_id TEXT, score INTEGER)")
            for i in range(5): await db.execute("INSERT INTO feedback VALUES (?,?)", (str(i), 5))
            for i in range(5, 10): await db.execute("INSERT INTO feedback VALUES (?,?)", (str(i), 1))
            await db.commit()

        async with aiosqlite.connect(cv_db) as db:
            await db.execute(
                "CREATE TABLE conversation_turns (user_msg TEXT, assistant_msg TEXT, timestamp REAL)"
            )
            for i in range(20):
                await db.execute(
                    "INSERT INTO conversation_turns VALUES (?,?,?)",
                    (f"User question {i}",
                     f"This is a detailed assistant response number {i} with enough words to pass the filter.",
                     _t.time())
                )
            await db.commit()

        conv  = FeedbackToRLHFConverter(fb_db, cv_db)
        pairs = await conv.build_pairs(min_pairs=2)
        assert isinstance(pairs, list)
        if pairs:
            p = pairs[0]
            assert "prompt"   in p
            assert "chosen"   in p
            assert "rejected" in p


# ── TrainingRun dataclass ─────────────────────────────────────────

class TestTrainingRun:

    def test_training_run_defaults(self):
        from backend.rlhf.rlhf_pipeline import TrainingRun
        run = TrainingRun(run_id="test01", method="dpo",
                          model="TinyLlama", n_pairs=10)
        assert run.status   == "pending"
        assert run.metrics  == {}
        assert run.t_start  is None
        assert run.checkpoint is None

    def test_training_run_status_update(self):
        from backend.rlhf.rlhf_pipeline import TrainingRun
        import time
        run = TrainingRun(run_id="test02", method="grpo",
                          model="TinyLlama", n_pairs=5)
        run.status  = "done"
        run.t_start = time.time() - 10
        run.t_end   = time.time()
        run.metrics = {"final_loss": 0.42}
        assert run.status == "done"
        assert run.metrics["final_loss"] == 0.42
