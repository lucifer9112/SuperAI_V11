---
name: project-development
description: LLM project development methodology - iterative building, testing, deployment
triggers: [project, develop, build, plan, architecture, methodology, workflow, sprint]
category: development
auto_activate: true
priority: 5
---

# Project Development Methodology

Meta-level practices for building LLM-powered projects.

## Development Phases
1. **Define** — clear objectives, constraints, success criteria
2. **Prototype** — minimal viable agent; test core capability first
3. **Evaluate** — measure against rubric before building more
4. **Iterate** — improve based on evaluation; one variable at a time
5. **Harden** — add error handling, rate limits, monitoring
6. **Deploy** — staged rollout with monitoring

## Key Practices
- **Test early, test often** — build evaluation before building features
- **One change at a time** — when debugging, change one variable per experiment
- **Log everything** — full traces of model inputs/outputs for debugging
- **Version prompts** — treat prompts as code; version control them
- **Measure cost** — track tokens-per-task as a first-class metric

## Common Mistakes
- Building features before evaluation framework exists
- Changing multiple things at once when debugging
- Not logging model inputs/outputs
- Optimizing for benchmarks instead of user outcomes
- Skipping the prototype phase

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
