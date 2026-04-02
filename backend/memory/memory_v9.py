"""
Legacy compatibility shim for removed V9 memory service.

Importing this module remains supported so older code paths and regression
tests can detect the deprecation explicitly, but the old implementation is no
longer available in V11.
"""

from __future__ import annotations


def __getattr__(name: str):
    if name == "MemoryServiceV9":
        raise ImportError("memory_v9 is no longer available in SuperAI V11")
    raise AttributeError(name)
