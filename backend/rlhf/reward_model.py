"""
SuperAI V11 — backend/rlhf/reward_model.py
STEP 1: RLHF — Reward Model

Two-layer system:
  1. HeuristicRewardEstimator  — instant scoring, no GPU, always available
  2. NeuralRewardModel         — sentence-transformer head, trained on feedback pairs

Neural architecture:
  BAAI/bge-small-en-v1.5 (frozen) → 384-dim embeddings
  [prompt_emb || response_emb] → Linear(768,256) → ReLU → Dropout
  → Linear(256,64) → ReLU → Linear(64,1) → Tanh → scalar [-1,+1]

Training: Bradley-Terry preference loss on (preferred, rejected) pairs
"""
from __future__ import annotations
import asyncio, json, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


@dataclass
class RewardScore:
    prompt:     str
    response:   str
    score:      float    # -1.0 to +1.0
    confidence: float    # 0.0 to 1.0
    method:     str      # "model" | "heuristic"


class HeuristicRewardEstimator:
    """Fast rule-based reward — no GPU, <1ms."""
    _HEDGES   = ["i think","i believe","maybe","perhaps","not sure",
                 "i'm uncertain","i don't know","unclear"]
    _QUALITY  = ["for example","specifically","step 1","step 2","because",
                 "therefore","research shows","in conclusion"]

    def score(self, prompt: str, response: str) -> RewardScore:
        if not response or len(response.strip()) < 5:
            return RewardScore(prompt, response, -0.8, 0.9, "heuristic")
        words   = response.split()
        n       = len(words)
        reward  = 0.0
        if   n < 10:  reward -= 0.4
        elif n < 30:  reward -= 0.1
        elif n > 500: reward -= 0.15
        else:         reward += 0.1
        reward -= min(sum(0.08 for h in self._HEDGES  if h in response.lower()), 0.30)
        reward += min(sum(0.07 for q in self._QUALITY if q in response.lower()), 0.25)
        if any(kw in response.lower() for kw in ["i cannot","i'm unable","i can't help"]):
            reward -= 0.3
        if "```" in response:
            reward += 0.12
        return RewardScore(prompt, response, round(max(-1.0,min(1.0,reward)), 3), 0.6, "heuristic")


class NeuralRewardModel:
    """
    Sentence-transformer + linear head reward model.
    Trained with Bradley-Terry preference loss.
    """
    DEFAULT_PATH = "data/reward_model/reward_head.pt"

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._path        = Path(model_path or self.DEFAULT_PATH)
        self._embedder    = None
        self._head        = None
        self._ready       = False
        self._is_training = False

    async def init(self) -> bool:
        try:
            def _load():
                from sentence_transformers import SentenceTransformer
                import torch, torch.nn as nn
                embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
                dim      = embedder.get_sentence_embedding_dimension()  # 384
                head = nn.Sequential(
                    nn.Linear(dim*2, 256), nn.ReLU(), nn.Dropout(0.1),
                    nn.Linear(256, 64),    nn.ReLU(),
                    nn.Linear(64, 1),      nn.Tanh(),
                )
                if self._path.exists():
                    state = torch.load(self._path, map_location="cpu")
                    head.load_state_dict(state)
                    logger.info("Reward head loaded", path=str(self._path))
                else:
                    logger.info("Reward head initialised (untrained)")
                return embedder, head
            self._embedder, self._head = await asyncio.to_thread(_load)
            self._ready = True
            return self._path.exists()
        except Exception as e:
            logger.warning("NeuralRewardModel init failed", error=str(e))
            return False

    async def score(self, prompt: str, response: str) -> float:
        if not self._ready: return 0.0
        def _fwd():
            import torch, numpy as np
            pe = self._embedder.encode([prompt[:256]],   normalize_embeddings=True)
            re = self._embedder.encode([response[:512]], normalize_embeddings=True)
            x  = torch.tensor(np.concatenate([pe, re], axis=1), dtype=torch.float32)
            with torch.no_grad():
                return float(self._head(x).squeeze().item())
        try:   return await asyncio.to_thread(_fwd)
        except Exception as e:
            logger.warning("NeuralRewardModel score failed", error=str(e))
            return 0.0

    async def train(self, pairs: List[Dict], epochs: int = 5, lr: float = 2e-4) -> Dict:
        if self._is_training: return {"error": "already_training"}
        if not self._ready: await self.init()
        if len(pairs) < 4: return {"error": "not_enough_pairs", "count": len(pairs)}
        self._is_training = True
        logger.info("Reward model training", pairs=len(pairs), epochs=epochs)
        try:
            return await asyncio.to_thread(self._train_sync, pairs, epochs, lr)
        finally:
            self._is_training = False

    def _train_sync(self, pairs: List[Dict], epochs: int, lr: float) -> Dict:
        import torch, torch.nn as nn, numpy as np
        emb_p  = torch.tensor(self._embedder.encode(
            [p["prompt"][:256]    for p in pairs], normalize_embeddings=True), dtype=torch.float32)
        resp_p = torch.tensor(self._embedder.encode(
            [p["preferred"][:512] for p in pairs], normalize_embeddings=True), dtype=torch.float32)
        resp_r = torch.tensor(self._embedder.encode(
            [p["rejected"][:512]  for p in pairs], normalize_embeddings=True), dtype=torch.float32)
        x_pos  = torch.cat([emb_p, resp_p], dim=1)
        x_neg  = torch.cat([emb_p, resp_r], dim=1)
        opt    = torch.optim.AdamW(self._head.parameters(), lr=lr, weight_decay=0.01)
        losses = []
        self._head.train()
        for _ in range(epochs):
            opt.zero_grad()
            loss = -torch.log(torch.sigmoid(
                self._head(x_pos).squeeze() - self._head(x_neg).squeeze()
            ) + 1e-8).mean()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self._head.parameters(), 1.0)
            opt.step()
            losses.append(round(float(loss.item()), 4))
        self._head.eval()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self._head.state_dict(), self._path)
        return {"epochs": epochs, "pairs": len(pairs),
                "final_loss": losses[-1], "loss_curve": losses, "path": str(self._path)}


class RewardModel:
    """Primary reward interface — neural when trained, heuristic fallback."""
    def __init__(self, model_path: Optional[str] = None) -> None:
        self._heuristic  = HeuristicRewardEstimator()
        self._neural     = NeuralRewardModel(model_path)
        self._use_neural = False

    async def init(self) -> None:
        self._use_neural = await self._neural.init()
        logger.info("RewardModel ready", neural=self._use_neural)

    async def score(self, prompt: str, response: str) -> RewardScore:
        if self._use_neural:
            s = await self._neural.score(prompt, response)
            return RewardScore(prompt, response, s, 0.85, "model")
        return self._heuristic.score(prompt, response)

    async def train(self, pairs: List[Dict], epochs: int = 5) -> Dict:
        result = await self._neural.train(pairs, epochs)
        if "error" not in result: self._use_neural = True
        return result

    def status(self) -> Dict:
        return {"use_neural": self._use_neural,
                "path": str(self._neural._path),
                "trained": self._neural._path.exists(),
                "training": self._neural._is_training}
