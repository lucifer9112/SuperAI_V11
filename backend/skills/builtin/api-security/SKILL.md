---
name: api-security
description: API security best practices - authentication, authorization, rate limiting, input validation
triggers: [api security, auth, jwt, oauth, rate limit, cors, api key, token]
category: security
auto_activate: false
priority: 7
---

# API Security Best Practices

## Authentication
- Use JWT with short expiry (15min access, 7d refresh)
- Store refresh tokens server-side or in httpOnly cookies
- Never expose secrets in client code or URLs
- Implement password hashing with bcrypt/argon2

## Authorization
- Role-Based Access Control (RBAC) for simple cases
- Attribute-Based Access Control (ABAC) for complex rules
- Always check authorization server-side, never trust client

## Input Validation
- Validate ALL inputs (query params, body, headers, path params)
- Whitelist allowed values, don't blacklist bad ones
- Set max length on all string fields
- Sanitize HTML to prevent XSS

## Rate Limiting
- Per-user/IP rate limits on all endpoints
- Stricter limits on auth endpoints (login, register, password reset)
- Return 429 with Retry-After header
- Use sliding window or token bucket algorithm

Source: antigravity-awesome-skills
