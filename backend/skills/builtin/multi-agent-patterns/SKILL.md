---
name: multi-agent-patterns
description: Multi-agent architecture patterns - supervisor, swarm, hierarchical coordination
triggers: [multi-agent, parallel, agents, orchestrate, coordinate, delegate, swarm]
category: architectural
auto_activate: true
priority: 7
---

# Multi-Agent Architecture Patterns

Use multi-agent patterns when a single agent's context window cannot hold all task-relevant information.

## Three Dominant Patterns

### 1. Supervisor/Orchestrator
- Centralized control with clear task decomposition
- Single coordinator delegates to specialists, synthesizes results
- Best for: structured tasks with human oversight needs

### 2. Peer-to-Peer/Swarm
- Flexible exploration without rigid planning
- Any agent can transfer control via explicit handoff
- Best for: creative tasks where rigid planning is counterproductive

### 3. Hierarchical
- Layered abstraction (strategy → planning → execution)
- Each layer has its own context and detail level
- Best for: large-scale projects with complex coordination

## Key Design Principles
- **Context isolation** is the primary benefit — each agent operates in clean context
- Design explicit coordination protocols
- Implement consensus mechanisms that resist sycophancy
- Handle failures to prevent error propagation cascades
- Prefer isolated contexts over shared megacontexts

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
