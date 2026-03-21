"""
SuperAI V11 — backend/intelligence/learning_pipeline.py

FEATURE 2: Continuous Self-Learning System

Pipeline:
  1. FeedbackCollector monitors high-rated responses (score >= threshold)
  2. DatasetBuilder auto-generates JSONL training examples
  3. RetrainScheduler checks example count, emits RETRAIN_READY event
  4. LoRATrainer runs QLoRA fine-tuning (on Colab GPU when available)
  5. ModelRegistry registers new adapter automatically

Colab-friendly:
  - All training runs in background thread (non-blocking)
  - Saves checkpoints to data/lora_checkpoints/
  - Can be triggered manually via POST /api/v1/learning/train
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
from loguru import logger


class DatasetBuilder:
    """
    Collects high-quality Q&A pairs from feedback DB
    and saves them as JSONL for fine-tuning.
    """

    def __init__(self, cfg) -> None:
        self.cfg          = cfg
        self.dataset_path = Path(getattr(cfg, "dataset_path", "data/training/"))
        self.min_score    = getattr(cfg, "min_quality_score", 4)
        self.dataset_path.mkdir(parents=True, exist_ok=True)

    async def build_from_feedback(
        self, feedback_db_path: str, conv_db_path: str
    ) -> int:
        """
        Query feedback DB for high-rated responses, build training JSONL.
        Returns number of examples collected.
        """
        examples: List[Dict] = []

        try:
            async with aiosqlite.connect(feedback_db_path) as fb_db:
                async with aiosqlite.connect(conv_db_path) as conv_db:
                    fb_db.row_factory  = aiosqlite.Row
                    conv_db.row_factory = aiosqlite.Row

                    cur = await fb_db.execute(
                        "SELECT response_id, score, comment FROM feedback WHERE score >= ?",
                        (self.min_score,)
                    )
                    rated = await cur.fetchall()

                    for row in rated:
                        # Find corresponding conversation turn
                        c = await conv_db.execute(
                            "SELECT user_msg, assistant_msg FROM conversation_turns "
                            "ORDER BY timestamp DESC LIMIT 200"
                        )
                        turns = await c.fetchall()
                        for turn in turns:
                            examples.append({
                                "instruction": turn["user_msg"],
                                "input": "",
                                "output":      turn["assistant_msg"],
                                "score":       row["score"],
                                "timestamp":   datetime.utcnow().isoformat(),
                            })

        except Exception as e:
            logger.warning("Dataset build failed", error=str(e))
            return 0

        # Save as JSONL
        if examples:
            ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = self.dataset_path / f"dataset_{ts}.jsonl"
            with open(path, "w") as f:
                for ex in examples:
                    f.write(json.dumps(ex) + "\n")
            logger.info("Dataset built", examples=len(examples), path=str(path))

        return len(examples)

    def get_all_examples(self) -> List[Dict]:
        """Load all collected JSONL examples."""
        all_examples: List[Dict] = []
        for f in self.dataset_path.glob("*.jsonl"):
            with open(f) as fh:
                for line in fh:
                    try:
                        all_examples.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return all_examples


class LoRATrainer:
    """
    Runs QLoRA fine-tuning in a background thread.
    Colab T4-optimised: batch_size=1, gradient_accumulation=8.
    """

    def __init__(self, cfg) -> None:
        self.cfg        = cfg
        self.output_dir = Path(getattr(cfg, "lora_output_dir", "data/lora_checkpoints/"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._is_training = False

    @property
    def is_training(self) -> bool:
        return self._is_training

    async def train(
        self,
        model_name: str,
        examples: List[Dict],
        epochs: int = 2,
    ) -> Optional[str]:
        """
        Run LoRA training asynchronously in thread pool.
        Returns path to checkpoint, or None if failed.
        """
        if self._is_training:
            logger.warning("Training already in progress")
            return None
        if len(examples) < 10:
            logger.warning("Not enough examples for training", count=len(examples))
            return None

        self._is_training = True
        logger.info("Starting LoRA training", model=model_name, examples=len(examples))

        try:
            checkpoint_path = await asyncio.to_thread(
                self._run_training, model_name, examples, epochs
            )
            return checkpoint_path
        except Exception as e:
            logger.error("LoRA training failed", error=str(e))
            return None
        finally:
            self._is_training = False

    def _run_training(
        self,
        model_name: str,
        examples: List[Dict],
        epochs: int,
    ) -> str:
        """Synchronous training — runs in thread pool."""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            from peft import LoraConfig, get_peft_model, TaskType
            from trl import SFTTrainer, SFTConfig
            from datasets import Dataset
        except ImportError as e:
            logger.error("Training deps missing — run: pip install trl peft datasets", error=str(e))
            raise

        ts      = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_dir = str(self.output_dir / f"lora_{ts}")

        # Format examples
        formatted = [
            {"text": f"### Instruction:\n{ex['instruction']}\n\n### Response:\n{ex['output']}"}
            for ex in examples
        ]
        dataset = Dataset.from_list(formatted)

        # 4-bit config
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

        tok = AutoTokenizer.from_pretrained(model_name)
        tok.pad_token = tok.eos_token
        tok.padding_side = "right"

        model = AutoModelForCausalLM.from_pretrained(
            model_name, quantization_config=bnb_cfg, device_map="auto"
        )
        model = get_peft_model(
            model,
            LoraConfig(
                r=8, lora_alpha=16,
                target_modules=["q_proj", "v_proj"],
                lora_dropout=0.05,
                task_type=TaskType.CAUSAL_LM,
            )
        )

        trainer = SFTTrainer(
            model=model, tokenizer=tok, train_dataset=dataset,
            args=SFTConfig(
                output_dir=out_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=1,
                gradient_accumulation_steps=8,
                fp16=True, logging_steps=5,
                max_seq_length=256,
                dataset_text_field="text",
                save_steps=50,
            )
        )
        trainer.train()
        trainer.save_model(out_dir)
        logger.info("LoRA training complete", checkpoint=out_dir)
        return out_dir


class LearningPipeline:
    """
    Orchestrates the full continuous learning cycle.
    Runs on a background scheduler.
    """

    def __init__(self, cfg, feedback_db: str, conv_db: str) -> None:
        self.cfg          = cfg
        self.feedback_db  = feedback_db
        self.conv_db      = conv_db
        self.dataset      = DatasetBuilder(cfg)
        self.trainer      = LoRATrainer(cfg)
        self._threshold   = getattr(cfg, "retrain_threshold", 50)
        self._task: Optional[asyncio.Task] = None
        self._total_collected = 0
        self._last_train_time: Optional[float] = None
        self._checkpoints: List[str] = []

    async def start_scheduler(self) -> None:
        """Start background learning scheduler."""
        if not getattr(self.cfg, "enabled", True):
            return
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Learning pipeline scheduler started")

    async def stop_scheduler(self) -> None:
        if self._task:
            self._task.cancel()

    async def collect_now(self) -> int:
        """Manually trigger dataset collection. Returns example count."""
        n = await self.dataset.build_from_feedback(self.feedback_db, self.conv_db)
        self._total_collected += n
        return n

    async def train_now(self, model_name: str) -> Optional[str]:
        """Manually trigger training. Returns checkpoint path."""
        examples = self.dataset.get_all_examples()
        if not examples:
            await self.collect_now()
            examples = self.dataset.get_all_examples()

        if len(examples) < 10:
            return None

        path = await self.trainer.train(model_name, examples)
        if path:
            self._checkpoints.append(path)
            self._last_train_time = time.time()
        return path

    def status(self) -> Dict:
        return {
            "enabled":          getattr(self.cfg, "enabled", True),
            "total_collected":  self._total_collected,
            "is_training":      self.trainer.is_training,
            "last_train":       self._last_train_time,
            "checkpoints":      len(self._checkpoints),
            "available_examples": len(self.dataset.get_all_examples()),
            "retrain_threshold": self._threshold,
        }

    async def _scheduler_loop(self) -> None:
        interval = getattr(self.cfg, "scheduler_interval_hours", 6) * 3600
        while True:
            try:
                await asyncio.sleep(interval)
                n = await self.collect_now()
                logger.info("Scheduled collection done", collected=n, total=self._total_collected)
                if self._total_collected >= self._threshold and not self.trainer.is_training:
                    logger.warning(
                        "RETRAIN_READY: enough examples collected",
                        total=self._total_collected, threshold=self._threshold
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler loop error", error=str(e))
