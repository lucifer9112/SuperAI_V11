---
name: bdi-mental-states
description: BDI cognitive modeling - Belief-Desire-Intention architecture for rational agent reasoning
triggers: [belief, desire, intention, cognitive, reasoning, mental state, bdi, rational, goal]
category: cognitive
auto_activate: true
priority: 8
---

# BDI Mental State Modeling

Formal cognitive architecture for rational agent systems using Belief-Desire-Intention (BDI) model.

## Mental States (Persistent)
- **Belief** — what the agent holds true about the world. Ground every belief in observable facts.
- **Desire** — what the agent wishes to bring about. Link each desire to motivating beliefs.
- **Intention** — what the agent commits to achieving. Must fulfill a desire and specify a plan.

## Mental Processes (Events)
- **BeliefProcess** — triggers belief formation/update from perception
- **DesireProcess** — generates desires from existing beliefs
- **IntentionProcess** — commits to selected desires as actionable intentions

## Cognitive Chain Pattern
Wire beliefs → desires → intentions into directed chains:
1. Agent perceives world state → forms Belief
2. Belief motivates → Desire
3. Desire is fulfilled by → Intention
4. Intention specifies → Plan (ordered tasks)

## Goal-Directed Planning
- Connect intentions to plans via specification
- Decompose plans into ordered task sequences
- Track which beliefs support which intentions
- Enable backward tracing: "why did the agent act?"

## Key Principles
- Always ground mental states in world state references (not free-text)
- Use bidirectional links (motivates/isMotivatedBy, fulfils/isFulfilledBy)
- Enable both forward reasoning and backward explanation
- Track temporal dimensions for all mental states

Source: muratcankoylan/Agent-Skills-for-Context-Engineering (BDI ontology by Peking University)
