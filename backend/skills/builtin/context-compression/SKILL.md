---
name: context-compression
description: Strategies for compressing context while preserving signal - summarization, anchored iterative compression
triggers: [compress, summarize, too long, token limit, truncate, shorten, reduce context]
category: foundational
auto_activate: true
priority: 8
---

# Context Compression Strategies

Optimize for tokens-per-task, not tokens-per-request.

## Three-Phase Compression Workflow
1. **Categorize** — classify context by signal value (critical, supporting, noise)
2. **Compress** — apply method based on category (keep critical verbatim, summarize supporting, drop noise)
3. **Validate** — probe compressed context to verify key information survives

## Compression Methods (ordered by quality preservation)
1. **Selective omission** — remove noise tokens entirely (safest)
2. **Structured summarization** — mandatory sections: decisions made, open questions, key facts
3. **Anchored iterative summarization** — compress in rounds, anchoring on key entities
4. **Extractive compression** — pull key sentences verbatim
5. **Abstractive compression** — model-generated summaries (highest risk of information loss)

## Score Across Six Dimensions
| Dimension | What to Measure |
|-----------|----------------|
| Faithfulness | Facts preserved accurately? |
| Completeness | Key info retained? |
| Relevance | Irrelevant info removed? |
| Coherence | Summary reads naturally? |
| Conciseness | Minimal token usage? |
| Actionability | Can agent act on compressed context? |

## Calibration
- Selective omission: 2-5x compression, ~0% info loss
- Structured summary: 5-10x compression, ~5% info loss
- Abstractive: 10-20x compression, ~15% info loss

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
