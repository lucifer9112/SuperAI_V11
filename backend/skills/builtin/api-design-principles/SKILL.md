---
name: api-design-principles
description: API shape, consistency, versioning, error handling best practices
triggers: [api design, rest, endpoint, versioning, api best practice, http, graphql]
category: architecture
auto_activate: true
priority: 6
---

# API Design Principles

## Core Rules
1. **Consistent naming** — plural nouns (`/users`), kebab-case, no verbs in URLs
2. **Proper HTTP methods** — GET (read), POST (create), PUT (replace), PATCH (update), DELETE
3. **Status codes** — 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 404 Not Found, 500 Server Error
4. **Pagination** — always paginate lists (`?page=1&limit=20`)
5. **Versioning** — URL prefix (`/v1/`), never break existing consumers

## Error Response Format
```json
{
  "error": {"code": "VALIDATION_ERROR", "message": "Email is required", "field": "email"}
}
```

## Security Checklist
- Rate limiting on all endpoints
- Input validation on all parameters
- Authentication on all non-public endpoints
- CORS configured for known origins only

Source: antigravity-awesome-skills
