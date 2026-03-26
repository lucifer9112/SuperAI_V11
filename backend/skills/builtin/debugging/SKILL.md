---
name: systematic-debugging
description: Systematic 4-phase debugging methodology for finding and fixing bugs
triggers: [debug, error, bug, fix, traceback, exception, crash]
category: debugging
auto_activate: true
priority: 5
---

# Systematic Debugging Skill

Follow this 4-phase process for every bug:

## Phase 1: Reproduce
- Identify the exact error message and conditions
- Create a minimal reproduction case
- Determine if the bug is consistent or intermittent

## Phase 2: Isolate
- Use binary search to narrow down the cause
- Rule out at least 2 other possible causes
- Identify the exact function/line causing the issue

## Phase 3: Fix
- Make the smallest possible change that fixes the root cause
- Avoid fixing symptoms — fix the underlying problem
- Consider side effects and regressions

## Phase 4: Verify
- Run the reproduction case to confirm the fix
- Run related tests to check for regressions
- Test edge cases around the fix
