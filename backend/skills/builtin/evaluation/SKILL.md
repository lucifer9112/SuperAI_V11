---
name: evaluation
description: Evaluation methods for agent systems - LLM-as-Judge, multi-dimensional rubrics, benchmarking
triggers: [evaluate, benchmark, test, measure, quality, score, judge, assess, metric]
category: operational
auto_activate: true
priority: 7
---

# Evaluation Methods for Agent Systems

## Core Principle
Evaluate outcomes, not execution paths. Agents may find alternative valid routes to goals.

## Multi-Dimensional Rubrics
Never use a single score. Capture:
- **Factual accuracy** — are facts correct?
- **Completeness** — is key info included?
- **Relevance** — is irrelevant info excluded?
- **Tool efficiency** — were tools used effectively?
- **Safety** — are outputs safe and appropriate?

## LLM-as-Judge Pattern
Use LLM evaluation for scalable testing across large test sets. Supplement with human review for edge cases, hallucinations, and subtle biases.

## The 95% Finding (BrowseComp Research)
| Factor | Variance Explained |
|--------|-------------------|
| Token usage | 80% |
| Tool calls | ~10% |
| Model choice | ~5% |

Implication: Better models + more tokens = dramatically better performance.

## Evaluation Types
1. **Unit eval** — single capability, deterministic pass/fail
2. **Integration eval** — multi-step workflow
3. **Regression eval** — new change doesn't break existing
4. **A/B eval** — compare two configurations

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
