---
name: docker-expert
description: Docker containerization - Dockerfile best practices, multi-stage builds, compose
triggers: [docker, container, dockerfile, compose, image, build, deploy, kubernetes, k8s]
category: devops
auto_activate: true
priority: 6
---

# Docker Expert

## Dockerfile Best Practices
1. Use specific base image tags (not `latest`)
2. Multi-stage builds to minimize image size
3. Copy requirements first, then code (better layer caching)
4. Use `.dockerignore` to exclude unnecessary files
5. Run as non-root user
6. One process per container

## Multi-Stage Build Template
```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
USER 1000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0"]
```

## Docker Compose
- Use named volumes for persistent data
- Define health checks for all services
- Set resource limits (memory, CPU)
- Use `.env` file for environment variables

Source: antigravity-awesome-skills
