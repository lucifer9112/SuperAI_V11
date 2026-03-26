---
name: architecture
description: System and component architecture design - patterns, trade-offs, scalability
triggers: [architecture, system design, component, microservice, monolith, scalable, design pattern]
category: architecture
auto_activate: true
priority: 8
---

# Architecture Design

## When to Activate
- Designing new systems or major features
- Evaluating build vs buy decisions
- Choosing between architectural patterns
- Reviewing system design for scalability

## Core Principles
1. **Start with requirements** — functional → non-functional → constraints
2. **Choose patterns deliberately** — monolith, microservices, event-driven, CQRS
3. **Design for change** — loose coupling, high cohesion, dependency inversion
4. **Document decisions** — Architecture Decision Records (ADRs)

## Decision Framework
| Pattern | When to Use | Trade-off |
|---------|------------|-----------|
| Monolith | Small teams, MVP | Simple but doesn't scale |
| Microservices | Multiple teams, complex domains | Scales but adds complexity |
| Event-driven | Async workflows, decoupling | Resilient but harder to debug |
| CQRS | Read/write asymmetry | Optimized but more code |

## Anti-Patterns to Avoid
- Big Ball of Mud (no structure)
- Golden Hammer (one pattern for everything)
- Premature optimization
- Distributed monolith

Source: antigravity-awesome-skills
