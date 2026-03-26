---
name: context-degradation
description: Detect and prevent context quality loss - lost-in-middle, poisoning, distraction, confusion
triggers: [degradation, quality loss, hallucination, wrong answer, context poison, attention drop]
category: foundational
auto_activate: true
priority: 8
---

# Context Degradation Patterns

Five degradation patterns destroy context quality:

## 1. Lost-in-Middle
Place critical information at context START and END. Middle positions suffer 10-40% reduced recall.

## 2. Context Poisoning
Once a hallucination or tool error enters context, it compounds through self-reference. Detection requires tracking claim provenance. Recovery: truncate to before the poisoning point.

## 3. Context Distraction
Even one irrelevant document degrades performance on relevant tasks. Models cannot "skip" irrelevant content. Filter aggressively BEFORE loading context.

## 4. Context Confusion
Multiple task types in one context cause cross-contamination. Models incorporate constraints from the wrong task. Use explicit task segmentation with separate context windows.

## 5. Context Clash
Contradictory-but-correct sources (version conflicts, perspective conflicts). Mark contradictions explicitly. Establish source precedence. Filter outdated versions.

## Mitigation Framework
1. **Prevent** — filter before loading
2. **Detect** — track provenance and monitor output quality
3. **Recover** — truncate or restart with verified-only context
4. **Isolate** — separate task contexts to prevent cross-contamination

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
