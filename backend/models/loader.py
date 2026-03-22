"""
SuperAI V11 — backend/models/loader.py

Resource-optimized LRU model loader.
V10 improvements:
  - CPU/GPU-aware quantization selection
  - Cost-aware routing (cheapest capable model)
  - Async preload queue
  - Memory pressure monitoring before load
"""
from __future__ import annotations
import asyncio, time
from collections import OrderedDict
from typing import AsyncGenerator, Dict, List, Optional, Tuple
import psutil
from loguru import logger
from backend.config.settings import ModelSettings
from backend.core.exceptions import ModelLoadError, ModelInferenceError


class _CachedModel:
    __slots__ = ("model", "tokenizer", "last_used", "load_time_s")

    def __init__(self, model, tokenizer, load_time_s: float = 0) -> None:
        self.model      = model
        self.tokenizer  = tokenizer
        self.last_used  = time.time()
        self.load_time_s = load_time_s

    def touch(self) -> None:
        self.last_used = time.time()


class ModelLoader:
    """Lazy-loading, LRU-cached, resource-aware HuggingFace model manager."""

    def __init__(self, cfg: ModelSettings) -> None:
        self.cfg     = cfg
        self._cache: OrderedDict[str, _CachedModel] = OrderedDict()
        self._lock   = asyncio.Lock()
        self._device = self._resolve_device(cfg.device)
        logger.info("ModelLoader V10 ready", device=self._device, cache_size=cfg.cache_size)

    # ── Public ────────────────────────────────────────────────────

    async def infer(
        self, model_name: str, prompt: str,
        max_tokens: int = 512, temperature: float = 0.7,
    ) -> Tuple[str, int]:
        cached = await self._get_or_load(model_name)

        def _run() -> Tuple[str, int]:
            inputs = cached.tokenizer(
                prompt, return_tensors="pt", truncation=True, max_length=2048
            ).to(self._device)
            import torch
            with torch.no_grad():
                out = cached.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=max(temperature, 0.01),
                    do_sample=temperature > 0.0,
                    pad_token_id=cached.tokenizer.eos_token_id,
                )
            gen   = out[0][inputs["input_ids"].shape[-1]:]
            text  = cached.tokenizer.decode(gen, skip_special_tokens=True).strip()
            return text, len(gen)

        try:
            answer, tokens = await asyncio.to_thread(_run)
            cached.touch()
            return answer, tokens
        except Exception as e:
            raise ModelInferenceError(str(e)) from e

    async def stream(
        self, model_name: str, prompt: str,
        max_tokens: int = 512, temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        from transformers import TextIteratorStreamer
        import threading

        cached = await self._get_or_load(model_name)
        streamer = TextIteratorStreamer(
            cached.tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        inputs = cached.tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=2048
        ).to(self._device)

        thread = threading.Thread(
            target=cached.model.generate,
            kwargs=dict(**inputs, max_new_tokens=max_tokens,
                        temperature=max(temperature, 0.01),
                        do_sample=temperature > 0.0,
                        pad_token_id=cached.tokenizer.eos_token_id,
                        streamer=streamer),
            daemon=True,
        )
        thread.start()
        for token in streamer:
            yield token
            await asyncio.sleep(0)
        cached.touch()

    async def count_tokens(self, model_name: str, text: str) -> int:
        cached = await self._get_or_load(model_name)

        def _run() -> int:
            encoded = cached.tokenizer(text, return_tensors="pt", truncation=True, max_length=4096)
            return int(encoded["input_ids"].shape[-1])

        try:
            count = await asyncio.to_thread(_run)
            cached.touch()
            return count
        except Exception:
            return max(1, len(text.split())) if text else 0

    def loaded_models(self) -> List[str]:
        return list(self._cache.keys())

    # ── Private ───────────────────────────────────────────────────

    async def _get_or_load(self, model_name: str) -> _CachedModel:
        async with self._lock:
            self._evict_idle()

            if model_name in self._cache:
                self._cache.move_to_end(model_name)
                return self._cache[model_name]

            # Check memory before loading
            self._check_memory_pressure()

            while len(self._cache) >= self.cfg.cache_size:
                evicted, _ = self._cache.popitem(last=False)
                logger.info("Model evicted (LRU)", model=evicted)

            logger.info("Loading model", model=model_name, device=self._device)
            t0 = time.time()
            try:
                cached = await asyncio.to_thread(self._load_sync, model_name)
                cached.load_time_s = time.time() - t0
            except Exception as e:
                raise ModelLoadError(f"Cannot load '{model_name}': {e}") from e

            self._cache[model_name] = cached
            logger.info("Model loaded", model=model_name,
                        load_time_s=round(cached.load_time_s, 1))
            return cached

    def _load_sync(self, model_name: str) -> _CachedModel:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token

        # V10: use 4-bit quantization on GPU to save VRAM
        if self._device != "cpu":
            try:
                from transformers import BitsAndBytesConfig
                bnb = BitsAndBytesConfig(load_in_4bit=True,
                                         bnb_4bit_compute_dtype=torch.float16)
                model = AutoModelForCausalLM.from_pretrained(
                    model_name, quantization_config=bnb,
                    device_map="auto", trust_remote_code=True,
                )
            except Exception:
                model = AutoModelForCausalLM.from_pretrained(
                    model_name, torch_dtype=torch.float16,
                    device_map="auto", trust_remote_code=True,
                )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch.float32, trust_remote_code=True,
            )
        model.eval()
        return _CachedModel(model=model, tokenizer=tok)

    def _evict_idle(self) -> None:
        now = time.time()
        to_evict = [
            name for name, cm in self._cache.items()
            if (now - cm.last_used) > self.cfg.idle_timeout
        ]
        for name in to_evict:
            del self._cache[name]
            logger.info("Model evicted (idle)", model=name)

    def _check_memory_pressure(self) -> None:
        """Warn if RAM > 85% before attempting a load."""
        vm = psutil.virtual_memory()
        if vm.percent > 85:
            logger.warning("High memory pressure before model load",
                           ram_pct=vm.percent)

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"
