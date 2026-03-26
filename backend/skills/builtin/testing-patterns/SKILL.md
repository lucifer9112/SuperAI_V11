---
name: testing-patterns
description: Testing best practices - unit, integration, E2E, test structure, mocking
triggers: [test, unit test, integration test, e2e, mock, fixture, coverage, pytest, jest]
category: quality
auto_activate: true
priority: 7
---

# Testing Patterns

## Test Pyramid
1. **Unit tests** (70%) — fast, isolated, test single functions
2. **Integration tests** (20%) — test component interactions
3. **E2E tests** (10%) — test full user flows

## Test Structure (AAA)
```python
def test_user_creation():
    # Arrange
    user_data = {"name": "Alice", "email": "alice@test.com"}

    # Act
    result = create_user(user_data)

    # Assert
    assert result.name == "Alice"
    assert result.id is not None
```

## Naming Convention
`test_[unit]_[scenario]_[expected]`
- `test_login_with_valid_credentials_returns_token`
- `test_create_user_with_duplicate_email_raises_error`

## Mocking Rules
- Mock external dependencies (APIs, databases, file system)
- Never mock the unit under test
- Prefer fakes over mocks for complex dependencies
- Reset mocks between tests

Source: antigravity-awesome-skills
