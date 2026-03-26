---
name: debugging-strategies
description: Systematic troubleshooting and debugging methodology
triggers: [debug, troubleshoot, error, crash, bug, stack trace, exception, fix]
category: quality
auto_activate: true
priority: 8
---

# Debugging Strategies

## Systematic Process
1. **Reproduce** — get reliable repro steps (if you can't reproduce, you can't fix)
2. **Isolate** — binary search to narrow the problem area
3. **Hypothesize** — form a theory about what's wrong
4. **Test** — change one thing to test your theory
5. **Fix** — apply minimal fix
6. **Verify** — confirm fix and check for regressions

## Quick Triage
| Symptom | First Check |
|---------|------------|
| Import error | Missing package or wrong path |
| Attribute error | Wrong type or None |
| Timeout | Network issue or infinite loop |
| Memory error | Large data or leak |
| Encoding error | UTF-8 handling |

## Tools
- **Print/log debugging** — add strategic logging at boundaries
- **Debugger** — pdb (Python), Chrome DevTools (JS)
- **Profiler** — cProfile (Python), Chrome Performance (JS)
- **Git bisect** — find which commit introduced the bug

## Golden Rule
Change ONE thing at a time. If you change multiple things, you won't know which fixed it.

Source: antigravity-awesome-skills
