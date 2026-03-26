---
name: create-pr
description: Package work into a clean, reviewable pull request
triggers: [pull request, pr, merge, review, commit, git, branch]
category: quality
auto_activate: false
priority: 4
---

# Create PR

## PR Structure
1. **Title** — concise, imperative (`Add user auth`, not `Added auth`)
2. **Description** — what changed, why, how to test
3. **Scope** — one logical change per PR (< 500 lines ideal)

## PR Template
```markdown
## What
[Brief description of the change]

## Why
[Motivation / issue reference]

## How
[Key implementation decisions]

## Testing
- [ ] Unit tests pass
- [ ] Manual testing done
- [ ] No regressions

## Screenshots
[If UI changes]
```

## Commit Messages
- `feat: add user authentication`
- `fix: resolve login timeout`
- `refactor: extract validation logic`
- `docs: update API documentation`
- `test: add integration tests for auth`

Source: antigravity-awesome-skills
