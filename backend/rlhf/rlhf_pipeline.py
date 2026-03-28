"""
SuperAI V11 — backend/rlhf/rlhf_pipeline.py
STEP 1: RLHF — Training Pipeline (DPO + GRPO)

DPO (Direct Preference Optimisation):
  - Input: (prompt, chosen_response, rejected_response) triples
  - Loss: -log σ(β * log π(chosen|x)/π_ref(chosen|x) - β * log π(rejected|x)/π_ref(rejected|x))
  - Requires trl>=0.12, peft, bitsandbytes
  - Colab T4 safe: LoRA r=8, batch=1, grad_accum=8

GRPO (Group Relative Policy Optimisation):
  - Input: prompts only — model generates groups of responses
  - Reward function: HeuristicRewardEstimator or trained NeuralRewardModel
  - Lower VRAM than PPO (no critic network needed)

FeedbackToRLHFConverter:
  - Queries existing feedback.db + conversation_turns
  - Pairs high-rated (≥4★) vs low-rated (≤2★) responses
  - Falls back to truncated-response pairs if not enough natural pairs
"""
from __future__ import annotations
import asyncio, json, time, uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import aiosqlite
from loguru import logger


@dataclass
class TrainingRun:
    run_id:     str
    method:     str        # "dpo" | "grpo"
    model:      str
    n_pairs:    int
    status:     str = "pending"
    metrics:    Dict = field(default_factory=dict)
    t_start:    Optional[float] = None
    t_end:      Optional[float] = None
    checkpoint: Optional[str] = None


class FeedbackToRLHFConverter:
    """Convert feedback DB rows → RLHF preference pairs."""

    def __init__(self, feedback_db: str, conv_db: str) -> None:
        self._fb   = feedback_db
        self._conv = conv_db

    async def build_pairs(self, min_pairs: int = 5) -> List[Dict[str, str]]:
        pairs: List[Dict] = []
        try:
            async with aiosqlite.connect(self._fb)   as fb_db:
                async with aiosqlite.connect(self._conv) as cv_db:
                    fb_db.row_factory  = aiosqlite.Row
                    cv_db.row_factory  = aiosqlite.Row
                    # Fetch rated turns
                    hi_cur = await fb_db.execute(
                        "SELECT response_id, score FROM feedback WHERE score >= 4 LIMIT 150")
                    lo_cur = await fb_db.execute(
                        "SELECT response_id, score FROM feedback WHERE score <= 2 LIMIT 150")
                    hi_rows = await hi_cur.fetchall()
                    lo_rows = await lo_cur.fetchall()

                    hi_turns = await self._fetch_turns_by_response_ids(
                        cv_db, [row["response_id"] for row in hi_rows if row["response_id"]]
                    )
                    lo_turns = await self._fetch_turns_by_response_ids(
                        cv_db, [row["response_id"] for row in lo_rows if row["response_id"]]
                    )

                    if not hi_turns:
                        hi_turns = await self._fetch_recent_turns(cv_db, len(hi_rows))
                    if not lo_turns:
                        lo_turns = await self._fetch_recent_turns(cv_db, len(lo_rows), reverse=True)

                    for i in range(min(len(hi_turns), len(lo_turns))):
                        h, l = hi_turns[i], lo_turns[i]
                        if len(h["a"].split()) >= 10 and len(l["a"].split()) >= 10:
                            pairs.append({"prompt": h["u"], "chosen": h["a"],
                                          "rejected": l["a"], "reward_diff": 2.0})

                    if len(pairs) < min_pairs:
                        logger.info(
                            "RLHF natural pairs below target; skipping synthetic truncation bootstrap",
                            available=len(pairs),
                            requested=min_pairs,
                        )
        except Exception as e:
            logger.warning("RLHF pair build failed", error=str(e))
        logger.info("RLHF pairs ready", count=len(pairs))
        return pairs

    async def _fetch_recent_turns(self, conn, limit: int, reverse: bool = False) -> List[Dict]:
        table, user_col, assistant_col, ts_col = await self._conversation_schema(conn)
        order = "DESC" if not reverse else "ASC"
        cur = await conn.execute(
            f"SELECT {user_col} AS user_text, {assistant_col} AS assistant_text FROM {table} "
            f"WHERE {assistant_col} != '' ORDER BY {ts_col} {order} LIMIT ?",
            (limit * 2,),
        )
        rows = await cur.fetchall()
        return [{"u": r["user_text"], "a": r["assistant_text"]}
                for r in rows if r["user_text"] and r["assistant_text"]]

    async def _fetch_turns_by_response_ids(self, conn, response_ids: List[str]) -> List[Dict]:
        ordered_ids = [rid for rid in response_ids if rid]
        if not ordered_ids:
            return []

        table, user_col, assistant_col, _ = await self._conversation_schema(conn)
        placeholders = ",".join("?" for _ in ordered_ids)
        cur = await conn.execute(
            f"SELECT response_id, {user_col} AS user_text, {assistant_col} AS assistant_text FROM {table} "
            f"WHERE response_id IN ({placeholders}) AND {assistant_col} != ''",
            ordered_ids,
        )
        rows = await cur.fetchall()
        by_id = {
            r["response_id"]: {"u": r["user_text"], "a": r["assistant_text"]}
            for r in rows
            if r["response_id"] and r["user_text"] and r["assistant_text"]
        }
        return [by_id[rid] for rid in ordered_ids if rid in by_id]

    async def _conversation_schema(self, conn) -> tuple[str, str, str, str]:
        candidates = [
            ("simple_conversation_turns", "user_text", "assistant_text", "created_at"),
            ("conversation_turns", "user_msg", "assistant_msg", "timestamp"),
        ]
        for table, user_col, assistant_col, ts_col in candidates:
            try:
                await conn.execute(
                    f"SELECT {user_col}, {assistant_col}, {ts_col} FROM {table} LIMIT 1"
                )
                return table, user_col, assistant_col, ts_col
            except Exception:
                continue
        raise RuntimeError("No supported conversation turns table found")


class DPOTrainer:
    """Direct Preference Optimisation on LoRA adapter."""

    def __init__(self, out_dir: str = "data/rlhf_checkpoints/") -> None:
        self._out_dir    = Path(out_dir)
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._is_running = False

    async def train(self, model_name: str, pairs: List[Dict],
                    epochs: int = 2, beta: float = 0.1, lr: float = 1e-5) -> TrainingRun:
        run = TrainingRun(run_id=str(uuid.uuid4())[:8], method="dpo",
                          model=model_name, n_pairs=len(pairs))
        if self._is_running:
            run.status  = "failed"
            run.metrics = {"error": "trainer_busy"}
            return run
        self._is_running  = True
        run.status        = "running"
        run.t_start       = time.time()
        try:
            m = await asyncio.to_thread(self._run_dpo, model_name, pairs, epochs, beta, lr, run.run_id)
            run.status     = "done"
            run.metrics    = m
            run.checkpoint = m.get("checkpoint")
        except Exception as e:
            run.status  = "failed"
            run.metrics = {"error": str(e)[:300]}
            logger.exception("DPO failed", run_id=run.run_id)
        finally:
            self._is_running = False
            run.t_end = time.time()
        return run

    def _run_dpo(self, model_name, pairs, epochs, beta, lr, run_id) -> Dict:
        try:
            from trl import DPOConfig, DPOTrainer as TRLDPO
            from peft import LoraConfig, get_peft_model, TaskType
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            from datasets import Dataset
            import torch
        except ImportError as e:
            raise ImportError(f"Run: pip install trl>=0.12.0 peft datasets — {e}")

        ts      = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_dir = str(self._out_dir / f"dpo_{run_id}_{ts}")
        bnb     = BitsAndBytesConfig(load_in_4bit=True,
                                      bnb_4bit_compute_dtype=torch.float16,
                                      bnb_4bit_quant_type="nf4")
        tok     = AutoTokenizer.from_pretrained(model_name)
        tok.pad_token = tok.eos_token
        model   = AutoModelForCausalLM.from_pretrained(
            model_name, quantization_config=bnb, device_map="auto")
        model   = get_peft_model(model, LoraConfig(
            r=8, lora_alpha=16, target_modules=["q_proj","v_proj"],
            lora_dropout=0.05, task_type=TaskType.CAUSAL_LM))
        ds      = Dataset.from_list([
            {"prompt": p["prompt"], "chosen": p["chosen"], "rejected": p["rejected"]}
            for p in pairs])
        trainer = TRLDPO(model=model, tokenizer=tok, train_dataset=ds,
            args=DPOConfig(output_dir=out_dir, num_train_epochs=epochs,
                per_device_train_batch_size=1, gradient_accumulation_steps=8,
                learning_rate=lr, beta=beta, fp16=True, logging_steps=5,
                save_steps=50, remove_unused_columns=False))
        trainer.train()
        trainer.save_model(out_dir)
        return {"method":"dpo","pairs":len(pairs),"epochs":epochs,"checkpoint":out_dir}


class GRPOTrainer:
    """Group Relative Policy Optimisation — lightweight PPO alternative."""

    def __init__(self, out_dir: str = "data/rlhf_checkpoints/") -> None:
        self._out_dir = Path(out_dir)
        self._out_dir.mkdir(parents=True, exist_ok=True)

    async def train(self, model_name: str, prompts: List[str],
                    epochs: int = 2) -> TrainingRun:
        run = TrainingRun(run_id=str(uuid.uuid4())[:8], method="grpo",
                          model=model_name, n_pairs=len(prompts),
                          status="running", t_start=time.time())
        try:
            m = await asyncio.to_thread(self._run_grpo, model_name, prompts, epochs, run.run_id)
            run.status     = "done"
            run.metrics    = m
            run.checkpoint = m.get("checkpoint")
        except Exception as e:
            run.status  = "failed"
            run.metrics = {"error": str(e)[:300]}
        run.t_end = time.time()
        return run

    def _run_grpo(self, model_name, prompts, epochs, run_id) -> Dict:
        try:
            from trl import GRPOConfig, GRPOTrainer as TRLGRPO
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            from datasets import Dataset
            import torch
        except ImportError as e:
            raise ImportError(f"Run: pip install trl>=0.12.0 — {e}")

        ts      = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_dir = str(self._out_dir / f"grpo_{run_id}_{ts}")
        bnb     = BitsAndBytesConfig(load_in_4bit=True,
                                      bnb_4bit_compute_dtype=torch.float16)
        tok     = AutoTokenizer.from_pretrained(model_name)
        tok.pad_token = tok.eos_token
        model   = AutoModelForCausalLM.from_pretrained(
            model_name, quantization_config=bnb, device_map="auto")
        ds      = Dataset.from_list([{"prompt": p} for p in prompts])

        from backend.rlhf.reward_model import HeuristicRewardEstimator
        _h = HeuristicRewardEstimator()
        def reward_fn(completions, prompts=None, **kw):
            return [_h.score(p or "", c).score
                    for p, c in zip(prompts or [""] * len(completions), completions)]

        trainer = TRLGRPO(model=model, tokenizer=tok,
            reward_funcs=reward_fn, train_dataset=ds,
            config=GRPOConfig(output_dir=out_dir, num_train_epochs=epochs,
                per_device_train_batch_size=1, learning_rate=1e-5,
                max_new_tokens=256, logging_steps=5, fp16=True))
        trainer.train()
        trainer.save_model(out_dir)
        return {"method":"grpo","prompts":len(prompts),"epochs":epochs,"checkpoint":out_dir}


class RLHFPipeline:
    """Main RLHF coordinator — manages reward model + training lifecycle."""

    def __init__(self, cfg, feedback_db: str, conv_db: str) -> None:
        self.cfg        = cfg
        self._converter = FeedbackToRLHFConverter(feedback_db, conv_db)
        out_dir         = getattr(cfg, "rlhf_output_dir", "data/rlhf_checkpoints/")
        self._dpo       = DPOTrainer(out_dir)
        self._grpo      = GRPOTrainer(out_dir)
        self._runs: List[TrainingRun] = []
        self._log_db    = Path(getattr(cfg, "rlhf_log_db", "data/rlhf_logs.db"))
        self._reward_model = None
        self._scheduler_task = None

    async def init(self) -> None:
        from backend.rlhf.reward_model import RewardModel
        reward_model_path = getattr(self.cfg, "reward_model_path", None)
        self._reward_model = RewardModel(model_path=reward_model_path)
        await self._reward_model.init()
        await self._init_db()
        # Start background scheduler
        interval = getattr(self.cfg, "rlhf_scheduler_hours", 24) * 3600
        self._scheduler_task = asyncio.create_task(self._scheduler_loop(interval))
        logger.info("RLHFPipeline ready")

    async def stop(self) -> None:
        if self._scheduler_task:
            self._scheduler_task.cancel()

    async def run_dpo(self, model_name: str, epochs: int = 2) -> TrainingRun:
        pairs = await self._converter.build_pairs(min_pairs=5)
        if len(pairs) < 4:
            return TrainingRun(run_id="none", method="dpo", model=model_name,
                               n_pairs=len(pairs), status="failed",
                               metrics={"error": f"Need >=4 pairs, got {len(pairs)}"})
        run = await self._dpo.train(model_name, pairs, epochs)
        self._runs.append(run)
        await self._log_run(run)
        return run

    async def run_grpo(self, model_name: str, prompts: List[str], epochs: int = 2) -> TrainingRun:
        run = await self._grpo.train(model_name, prompts, epochs)
        self._runs.append(run)
        await self._log_run(run)
        return run

    async def train_reward_model(self) -> Dict:
        pairs = await self._converter.build_pairs()
        rm_pairs = [{"prompt": p["prompt"], "preferred": p["chosen"],
                     "rejected": p["rejected"]} for p in pairs if p.get("chosen")]
        if len(rm_pairs) < 4:
            return {"error": "not_enough_pairs", "count": len(rm_pairs)}
        return await self._reward_model.train(rm_pairs)

    async def score_response(self, prompt: str, response: str) -> float:
        if not self._reward_model: return 0.0
        rs = await self._reward_model.score(prompt, response)
        return rs.score

    def status(self) -> Dict:
        return {
            "runs_total":   len(self._runs),
            "runs_done":    sum(1 for r in self._runs if r.status == "done"),
            "dpo_busy":     self._dpo._is_running,
            "reward_model": self._reward_model.status() if self._reward_model else {},
            "recent_runs":  [{"run_id":r.run_id,"method":r.method,"status":r.status,
                               "pairs":r.n_pairs} for r in self._runs[-5:]],
        }

    async def _scheduler_loop(self, interval: float) -> None:
        while True:
            try:
                await asyncio.sleep(interval)
                pairs = await self._converter.build_pairs()
                if len(pairs) >= getattr(self.cfg, "rlhf_min_pairs", 10):
                    logger.warning("RLHF_SCHEDULE: Enough pairs for training",
                                   pairs=len(pairs))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("RLHF scheduler error", error=str(e))

    async def _init_db(self) -> None:
        self._log_db.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._log_db) as db:
            await db.execute("""CREATE TABLE IF NOT EXISTS rlhf_runs (
                run_id TEXT PRIMARY KEY, method TEXT, model TEXT, n_pairs INT,
                status TEXT, metrics TEXT, t_start REAL, t_end REAL, checkpoint TEXT)""")
            await db.commit()

    async def _log_run(self, run: TrainingRun) -> None:
        try:
            async with aiosqlite.connect(self._log_db) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO rlhf_runs VALUES (?,?,?,?,?,?,?,?,?)",
                    (run.run_id, run.method, run.model, run.n_pairs, run.status,
                     json.dumps(run.metrics), run.t_start, run.t_end, run.checkpoint))
                await db.commit()
        except Exception as e:
            logger.warning("RLHF log failed", error=str(e))
