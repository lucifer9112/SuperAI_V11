---
name: memory-systems
description: Memory architecture design - layers, retrieval strategies, framework selection
triggers: [memory, remember, recall, store, knowledge, history, persist, session]
category: architectural
auto_activate: true
priority: 6
---

# Memory System Design

Think of memory as a spectrum from volatile context window to persistent storage.

## Memory Layers
1. **Context window** — immediate, volatile, highest quality retrieval
2. **Short-term buffer** — session-scoped, key-value or structured
3. **Long-term store** — persistent, requires retrieval strategy
4. **Knowledge graph** — entity relationships, multi-hop reasoning

## Default Strategy
Use the simplest layer that meets retrieval needs. Complexity matters less than reliable retrieval — filesystem agents with basic operations can beat specialized memory tools.

## Retrieval Strategies
- **Recency-weighted** — most recent memories first
- **Relevance-ranked** — semantic similarity search
- **Entity-anchored** — retrieve by entity mention
- **Temporal** — time-range queries

## Memory Consolidation
- Periodically summarize short-term into long-term
- Deduplicate entity mentions across sessions
- Decay low-access memories over time
- Preserve emotionally-tagged high-priority memories

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
