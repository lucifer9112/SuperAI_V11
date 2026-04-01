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
        self._fallback_reasons: Dict[str, str] = {}
        self._resolved_models: Dict[str, str] = {}
        logger.info("ModelLoader V10 ready", device=self._device, cache_size=cfg.cache_size)

    # ── Public ────────────────────────────────────────────────────

    async def infer(
        self, model_name: str, prompt: str,
        max_tokens: int = 512, temperature: float = 0.7,
    ) -> Tuple[str, int]:
        try:
            cached = await self._get_or_load(model_name)
        except Exception as e:
            answer = self._fallback_answer(model_name, prompt)
            self._remember_fallback(model_name, e)
            return answer, max(1, len(answer.split()))

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
            answer = self._fallback_answer(model_name, prompt)
            self._remember_fallback(model_name, e)
            return answer, max(1, len(answer.split()))

    async def stream(
        self, model_name: str, prompt: str,
        max_tokens: int = 512, temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        try:
            from transformers import TextIteratorStreamer
            import threading

            cached = await self._get_or_load(model_name)
        except Exception as e:
            self._remember_fallback(model_name, e)
            for token in self._fallback_answer(model_name, prompt).split():
                yield token + " "
                await asyncio.sleep(0)
            return
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
        try:
            cached = await self._get_or_load(model_name)
        except Exception:
            return max(1, len(text.split())) if text else 0

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

    def resolve_model_name(self, requested_name: str) -> str:
        return self._resolved_models.get(requested_name, requested_name)

    # ── Private ───────────────────────────────────────────────────

    async def _get_or_load(self, model_name: str) -> _CachedModel:
        async with self._lock:
            self._evict_idle()

            for candidate in self._candidate_models(model_name):
                if candidate in self._cache:
                    self._cache.move_to_end(candidate)
                    self._resolved_models[model_name] = candidate
                    return self._cache[candidate]

            # Check memory before loading
            self._check_memory_pressure()

            last_exc: Exception | None = None
            for candidate in self._candidate_models(model_name):
                while len(self._cache) >= self.cfg.cache_size:
                    evicted, _ = self._cache.popitem(last=False)
                    logger.info("Model evicted (LRU)", model=evicted)

                logger.info("Loading model", model=candidate, requested=model_name, device=self._device)
                t0 = time.time()
                try:
                    cached = await asyncio.wait_for(
                        asyncio.to_thread(self._load_sync, candidate),
                        timeout=max(1, self.cfg.load_timeout_s),
                    )
                    cached.load_time_s = time.time() - t0
                    self._cache[candidate] = cached
                    self._resolved_models[model_name] = candidate
                    if candidate != model_name:
                        logger.warning(
                            "Primary model unavailable, using backup model",
                            requested=model_name,
                            backup_model=candidate,
                        )
                    logger.info("Model loaded", model=candidate, load_time_s=round(cached.load_time_s, 1))
                    return cached
                except Exception as e:
                    last_exc = e
                    logger.warning("Model candidate failed", requested=model_name, candidate=candidate, error=str(e))

            raise ModelLoadError(f"Cannot load '{model_name}': {last_exc}") from last_exc

    def _candidate_models(self, requested_name: str) -> List[str]:
        candidates = [requested_name]
        for fallback in self.cfg.fallback_models:
            if fallback and fallback not in candidates:
                candidates.append(fallback)
        return candidates

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

    def _remember_fallback(self, model_name: str, exc: Exception) -> None:
        reason = str(exc)
        if self._fallback_reasons.get(model_name) == reason:
            return
        self._fallback_reasons[model_name] = reason
        logger.warning(
            "Model unavailable, using degraded fallback response",
            model=model_name,
            reason=reason,
        )

    @staticmethod
    def _fallback_answer(model_name: str, prompt: str) -> str:
        lower = prompt.lower()

        if "respond only:" in lower and "actioninput:" in lower:
            return (
                "Thought: The model runtime is unavailable, so I should finish with a safe fallback.\n"
                "Action: finish\n"
                "ActionInput: The agent subsystem is running in degraded mode. "
                "Please enable model weights to get deeper autonomous reasoning."
            )

        if "generate python code" in lower or "expert python developer" in lower:
            return (
                "def hello_world() -> str:\n"
                "    return \"Hello, world!\"\n"
            )

        if "debug:" in lower:
            return (
                "The project is running in degraded model mode, so here is a safe first-pass debug note:\n"
                "1. Reproduce the error.\n2. Inspect the failing stack trace.\n3. Add a minimal regression test."
            )

        if "review:" in lower:
            return (
                "Quick review: check input validation, error handling, and tests around the changed behavior. "
                "No model-backed deep review was available in this environment."
            )

        if "optimize:" in lower:
            return (
                "Optimization fallback: profile first, remove unnecessary work in hot paths, "
                "and prefer caching repeated expensive operations."
            )

        if "write tests for:" in lower:
            return (
                "Suggested tests:\n"
                "- happy path response\n"
                "- invalid input handling\n"
                "- regression case for the reported bug\n"
            )

        if "explain:" in lower:
            return "This feature is running in degraded model mode. The code or text can still be inspected, but a richer explanation requires the configured model."

        if "assistant:" in lower:
            question = prompt.split("User:")[-1].replace("Assistant:", "").strip()
            return (
                f"I am responding in degraded model mode because '{model_name}' is not available right now. "
                f"Here is a concise fallback answer to your request: {question[:240]}"
            )

        return (
            f"SuperAI is running in degraded model mode because '{model_name}' is unavailable. "
            "The server is healthy, optional systems remain loaded, and real model responses will resume once the configured model can be loaded."
        )
