---
name: react-patterns
description: React component patterns, hooks, state management, performance optimization
triggers: [react, component, hook, state, redux, next.js, jsx, tsx, virtual dom]
category: frontend
auto_activate: false
priority: 5
---

# React Patterns

## Component Patterns
- **Compound Components** — share implicit state (Tabs + TabPanel)
- **Render Props** — share behavior via function children
- **Custom Hooks** — extract reusable logic (useForm, useFetch)
- **HOC** — wrap components for cross-cutting concerns (withAuth)

## Performance
- `React.memo()` for expensive pure components
- `useMemo()` for expensive calculations
- `useCallback()` for stable callback references
- Lazy loading with `React.lazy()` + `Suspense`
- Virtual scrolling for large lists

## State Management
| Size | Tool |
|------|------|
| Local | useState, useReducer |
| Shared | Context + useReducer |
| Complex | Zustand, Jotai |
| Server state | TanStack Query, SWR |

## Anti-Patterns
- Prop drilling (use context or state library)
- useEffect for derived state (use useMemo)
- Giant components (split into smaller pieces)

Source: antigravity-awesome-skills
