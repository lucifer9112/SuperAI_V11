---
name: workflow-automation
description: CI/CD and workflow automation - GitHub Actions, pipelines, automated testing
triggers: [ci, cd, pipeline, github actions, automation, deploy, workflow, ci/cd]
category: devops
auto_activate: false
priority: 5
---

# Workflow Automation

## GitHub Actions Template
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff
      - run: ruff check .
```

## Pipeline Stages
1. **Lint** — code quality (fast, fail early)
2. **Test** — unit + integration tests
3. **Build** — compile/package
4. **Deploy** — staging → production

## Best Practices
- Cache dependencies between runs
- Run lint before tests (cheaper to fail early)
- Use matrix builds for multiple Python/Node versions
- Keep secrets in GitHub Secrets, never in code

Source: antigravity-awesome-skills
