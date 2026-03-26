---
name: code-review
description: Review code for bugs, style issues, security vulnerabilities, and performance
triggers: [review, code quality, check code, audit, lint]
category: quality
auto_activate: true
priority: 5
---

# Code Review Skill

When reviewing code, follow this systematic approach:

1. **Correctness First** — Look for bugs, logic errors, off-by-one errors, null/undefined handling
2. **Security Check** — Scan for injection vulnerabilities, unsafe operations, hardcoded secrets
3. **Performance** — Identify unnecessary allocations, N+1 queries, blocking I/O in async code
4. **Style & Readability** — Check naming conventions, function length, comment quality
5. **Edge Cases** — Consider empty inputs, boundary values, concurrent access

Rate each issue as:
- **Critical** — Will cause bugs or security issues in production
- **Warning** — Should be fixed before merge
- **Info** — Nice to have improvement
