---
name: typescript-expert
description: TypeScript best practices - strict mode, generics, utility types, patterns
triggers: [typescript, ts, type, interface, generic, enum, next.js, angular, node]
category: backend
auto_activate: false
priority: 5
---

# TypeScript Expert

## Strict Mode Rules
- Enable `strict: true` in tsconfig.json
- No `any` type — use `unknown` + type guards
- Prefer `interface` for objects, `type` for unions/intersections
- Use `readonly` for immutable properties

## Essential Utility Types
- `Partial<T>` — all properties optional
- `Required<T>` — all properties required
- `Pick<T, K>` — select specific properties
- `Omit<T, K>` — exclude specific properties
- `Record<K, V>` — key-value mapping

## Patterns
- Discriminated unions for state machines
- Generic constraints for type-safe APIs
- Zod for runtime validation + type inference
- Barrel exports for clean imports

Source: antigravity-awesome-skills
