---
name: context-optimization
description: Production optimization - KV-cache, observation masking, compaction, partitioning
triggers: [optimize, performance, latency, cost, tokens, cache, speed, slow]
category: operational
auto_activate: true
priority: 7
---

# Context Optimization Techniques

Apply in priority order — cheapest and safest first.

## 1. KV-Cache Optimization (Zero Risk)
Stabilize prompt structure so inference engine reuses cached Key/Value tensors. Reorder prompts to maximize cache hits. Immediate cost and latency savings.

## 2. Observation Masking (Low Risk)
Replace verbose tool outputs with compact references once processed. Tool outputs consume 80%+ of tokens in typical agent trajectories. Original content remains retrievable.

## 3. Compaction (Medium Risk — Lossy)
Summarize accumulated context when utilization exceeds 70%. Reinitialize with summary. Apply AFTER masking has removed low-value bulk.

## 4. Context Partitioning (Coordination Cost)
Split across sub-agents with isolated contexts when single window cannot hold the problem. Use when estimated context exceeds 60% of window limit.

## Performance Targets
- Latency: <2s for chat, <5s for complex tasks
- Token efficiency: >0.7 useful tokens per total tokens
- Cache hit rate: >80% for repeated prompt prefixes

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
