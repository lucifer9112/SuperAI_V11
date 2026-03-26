---
name: tool-design
description: Tool and function calling design patterns for agent systems
triggers: [tool, function, api, call, schema, parameter, capability]
category: architectural
auto_activate: true
priority: 5
---

# Tool Design for Agent Systems

Design tools as capability extensions that expand what agents can do beyond text generation.

## Tool Schema Principles
- **Clear descriptions** — the model selects tools based on descriptions, not code
- **Minimal parameters** — fewer required params = higher selection accuracy
- **Typed schemas** — use JSON Schema with explicit types and validation
- **Idempotent operations** — safe tools can retry without side effects

## Design Rules
1. One tool = one capability (no multi-purpose tools)
2. Output structured data, not prose
3. Include error states in the schema
4. Set reasonable timeouts
5. Log all tool invocations for debugging

## Safety Levels
- **Safe** — read-only, no side effects (search, calculate, read file)
- **Moderate** — reversible side effects (create file, update entry)
- **Dangerous** — irreversible (delete, execute code, send email)

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
