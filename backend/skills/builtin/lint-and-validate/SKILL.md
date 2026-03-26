---
name: lint-and-validate
description: Lightweight code quality checks - linting, formatting, type checking
triggers: [lint, format, validate, eslint, prettier, black, ruff, mypy, check]
category: quality
auto_activate: true
priority: 6
---

# Lint and Validate

## Python Stack
| Tool | Purpose | Command |
|------|---------|---------|
| Ruff | Linting + formatting | `ruff check . && ruff format .` |
| MyPy | Type checking | `mypy src/` |
| Black | Formatting | `black .` |
| isort | Import sorting | `isort .` |

## JavaScript/TypeScript Stack
| Tool | Purpose | Command |
|------|---------|---------|
| ESLint | Linting | `npx eslint .` |
| Prettier | Formatting | `npx prettier --write .` |
| TypeScript | Type checking | `npx tsc --noEmit` |

## Pre-Commit Checklist
1. No lint errors
2. No type errors
3. All tests pass
4. No hardcoded secrets
5. No console.log / print debugging left

Source: antigravity-awesome-skills
