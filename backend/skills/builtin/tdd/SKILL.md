---
name: test-driven-development
description: TDD workflow for writing tests before implementation
triggers: [test, tdd, unit test, testing, pytest, coverage]
category: testing
auto_activate: true
priority: 3
---

# Test-Driven Development Skill

Follow the Red-Green-Refactor cycle:

1. **Red** — Write a failing test that describes the desired behavior
2. **Green** — Write the minimum code to make the test pass
3. **Refactor** — Clean up the code while keeping tests green

### Test Structure
- Use descriptive test names: `test_should_return_error_when_input_is_empty`
- One assertion per test when possible
- Use fixtures for shared setup
- Mock external dependencies

### Coverage Goals
- Aim for 80%+ line coverage on new code
- 100% coverage on critical paths (auth, payments, data validation)
