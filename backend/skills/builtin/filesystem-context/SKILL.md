---
name: filesystem-context
description: Using filesystem as extended context for agent systems
triggers: [file, filesystem, directory, project, codebase, files, workspace]
category: architectural
auto_activate: true
priority: 4
---

# Filesystem as Context

Use the filesystem as an extended context window that persists across sessions.

## Strategy
- Treat files as retrieval-augmented context — load on demand, not pre-loaded
- Store intermediate results in structured files (JSON, YAML)
- Use directory structure as a knowledge hierarchy
- Index files for fast semantic search

## Patterns
1. **Scratchpad files** — temporary context that survives tool calls
2. **Knowledge bases** — structured facts that outlive sessions
3. **Progress checkpoints** — resume-friendly state snapshots
4. **Skill libraries** — reusable instruction sets (like this file)

## Key Insight
Letta's filesystem agents scored 74% on memory benchmarks using basic file operations, beating specialized memory tools at 68.5%. Simple filesystem access can be surprisingly powerful.

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
