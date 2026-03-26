---
name: prompt-engineer
description: Prompt engineering techniques - chain-of-thought, few-shot, structured output
triggers: [prompt, few-shot, chain of thought, system prompt, template, llm, gpt, claude]
category: ai-ml
auto_activate: true
priority: 7
---

# Prompt Engineer

## Techniques (ordered by reliability)
1. **System prompt** — set role, constraints, output format
2. **Few-shot examples** — show 2-3 input/output pairs
3. **Chain-of-thought** — "Think step by step before answering"
4. **Structured output** — force JSON/XML with schema
5. **Self-consistency** — generate multiple answers, pick majority

## Prompt Template
```
ROLE: You are a [specific expert role].
CONTEXT: [background information]
TASK: [exactly what to do]
FORMAT: [output structure]
CONSTRAINTS: [limitations and rules]
EXAMPLES:
  Input: [example input]
  Output: [example output]
```

## Anti-Patterns
- Vague instructions ("do a good job")
- Too many constraints (models ignore excess rules)
- Missing output format (unparseable responses)
- No examples for complex tasks

## Temperature Guide
| Task | Temperature |
|------|------------|
| Coding/math | 0.0-0.2 |
| Q&A/summarize | 0.3-0.5 |
| Creative writing | 0.7-1.0 |

Source: antigravity-awesome-skills
