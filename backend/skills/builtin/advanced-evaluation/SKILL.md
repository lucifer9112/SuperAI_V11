---
name: advanced-evaluation
description: Advanced evaluation techniques - LLM-as-Judge implementation, pairwise comparison, calibration
triggers: [advanced eval, judge, pairwise, calibrate, rubric, scoring, grading]
category: operational
auto_activate: true
priority: 6
---

# Advanced Evaluation Techniques

## LLM-as-Judge Implementation
Use a stronger model to evaluate a weaker model's output. Structure with:
1. **Clear rubric** — define exactly what "good" means for each dimension
2. **Reference answers** — provide gold-standard examples
3. **Structured output** — force JSON scores, not free-text ratings
4. **Position debiasing** — randomize order of candidates to avoid position bias

## Pairwise Comparison
Compare two outputs head-to-head instead of absolute scoring. More reliable because:
- Humans and models are better at relative judgments
- Eliminates scale calibration issues
- Works with: "Which response is better for X?"

## Calibration Strategy
- Run judge on known-quality examples first
- Measure agreement with human ratings
- Adjust rubric wording until agreement > 80%
- Re-calibrate periodically as model versions change

## Anti-Patterns
- Don't use the same model as both generator and judge
- Don't evaluate without a rubric (garbage in, garbage out)
- Don't trust single-dimension scores
- Don't skip human spot-checks on judge outputs

Source: muratcankoylan/Agent-Skills-for-Context-Engineering
