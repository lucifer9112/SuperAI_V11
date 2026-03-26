---
name: context-fundamentals
description: Core context engineering - attention budget management, token placement, progressive disclosure
triggers: [context, prompt, tokens, attention, context window, context engineering]
category: foundational
auto_activate: true
priority: 10
---

# Context Engineering Fundamentals

Treat context as a finite attention budget, not a storage bin. Every token competes for model attention.

## Core Principles
1. **Informativity over exhaustiveness** — include only what matters for the current decision
2. **Position-aware placement** — critical info at beginning/end (85-95% recall); middle drops to 76-82%
3. **Progressive disclosure** — load summaries first; full content only when needed
4. **Iterative curation** — context engineering is ongoing, not one-time prompt writing

## Context Budget
- Effective capacity: 60-70% of advertised window (not 100%)
- U-shaped attention curve penalizes middle-placed information
- Each added token depletes attention available for all other tokens

## Practical Rules
- Place constraints and critical instructions at START of context
- Place recent/important data at END of context
- Move "might need" information behind tool calls, don't pre-load
- Measure token usage; optimize for tokens-per-task, not tokens-per-request

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
