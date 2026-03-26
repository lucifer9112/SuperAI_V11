---
name: python-patterns
description: Python best practices - type hints, async, decorators, packaging, testing
triggers: [python, pip, fastapi, django, flask, async, decorator, typing, pydantic]
category: backend
auto_activate: true
priority: 6
---

# Python Patterns

## Code Quality
- Type hints on all function signatures
- Docstrings on public functions (Google or NumPy style)
- Dataclasses or Pydantic models for structured data
- Context managers for resource management
- f-strings for formatting (not % or .format)

## Async Patterns
- `async/await` for I/O-bound operations
- `asyncio.gather()` for concurrent tasks
- `aiohttp` for HTTP, `asyncpg` for database
- Never mix sync and async without `run_in_executor()`

## Project Structure
```
src/
  package/
    __init__.py
    models.py
    services.py
    api/
tests/
  unit/
  integration/
pyproject.toml
```

## Common Anti-Patterns
- Mutable default arguments (`def f(x=[])`)
- Bare `except:` (catch specific exceptions)
- Circular imports (restructure modules)
- God classes (split responsibilities)

Source: antigravity-awesome-skills
