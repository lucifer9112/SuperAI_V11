---
name: security-auditor
description: Security-focused code and API review - auth, injection, OWASP top 10
triggers: [security, audit, vulnerability, injection, xss, csrf, auth, owasp, penetration]
category: security
auto_activate: true
priority: 9
---

# Security Auditor

## OWASP Top 10 Checklist
1. **Injection** — SQL, NoSQL, OS command, LDAP injection
2. **Broken Authentication** — weak passwords, session fixation, missing MFA
3. **Sensitive Data Exposure** — unencrypted data, hardcoded secrets, verbose errors
4. **XML External Entities** — XXE attacks via XML parsers
5. **Broken Access Control** — IDOR, missing authorization, privilege escalation
6. **Security Misconfiguration** — default credentials, unnecessary features, verbose errors
7. **XSS** — reflected, stored, DOM-based cross-site scripting
8. **Insecure Deserialization** — untrusted data deserialization
9. **Known Vulnerabilities** — outdated dependencies, unpatched libraries
10. **Insufficient Logging** — missing audit trails, no alerting

## Code Review Flags
- `eval()`, `exec()`, `system()` — command injection risk
- String concatenation in SQL — SQL injection
- `innerHTML` — XSS risk
- Hardcoded passwords/API keys — secret exposure
- `pickle.loads()` — deserialization attack
- Missing input validation — all injection types

Source: antigravity-awesome-skills
