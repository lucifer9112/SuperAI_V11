---
name: hosted-agents
description: Patterns for deploying and hosting production agent systems
triggers: [deploy, production, host, scale, server, infrastructure, cloud]
category: architectural
auto_activate: true
priority: 4
---

# Hosted Agent Patterns

Design patterns for production agent deployments.

## Deployment Models
1. **Stateless API** — agent per request, context from external storage
2. **Stateful server** — persistent agent with session memory
3. **Queue-based** — async task processing with worker agents
4. **Hybrid** — stateless API + background workers for long tasks

## Production Considerations
- Set hard timeouts on all model calls (30s default)
- Implement circuit breakers for model API failures
- Rate limit per user/session
- Log all agent decisions for debugging
- Monitor token usage for cost control
- Implement graceful degradation when model unavailable

## Scaling Strategy
- Scale stateless agents horizontally
- Use sticky sessions for stateful agents
- Cache repeated model calls (same prompt = same response)
- Partition workload across specialized agent pools

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
