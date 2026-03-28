"""Deprecated legacy V9 memory module.

This compatibility module intentionally fails on legacy class access so the
active runtime does not silently route through outdated aliases.
"""

__all__: list[str] = []


def __getattr__(name: str):
    raise ImportError(
        "backend.memory.memory_v9 is no longer available. "
        "Use backend.services.simple_memory_service.SimpleMemoryService or "
        "backend.memory.advanced_memory.UnifiedMemoryRetriever instead."
    )
