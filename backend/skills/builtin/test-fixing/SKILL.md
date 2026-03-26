---
name: test-fixing
description: Systematic approach to fixing failing tests and test suite maintenance
triggers: [test fail, broken test, fix test, flaky, assertion error, test error]
category: quality
auto_activate: true
priority: 6
---

# Test Fixing

## Diagnosis Process
1. **Read the error** — assertion error vs runtime error vs timeout
2. **Reproduce** — run the failing test in isolation
3. **Bisect** — is it the test or the code that changed?
4. **Fix** — fix the root cause, not the symptom

## Common Failure Types
| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| AssertionError | Logic changed | Update test or fix code |
| ImportError | Missing dependency | Add to requirements |
| Timeout | Slow external call | Mock the dependency |
| Flaky (intermittent) | Race condition or state leakage | Isolate test, reset state |
| PermissionError | File system | Use temp dirs |

## Anti-Patterns
- Deleting failing tests instead of fixing them
- Adding `@skip` without a tracking issue
- Making tests less strict to pass
- Not running the full suite before committing

Source: antigravity-awesome-skills
