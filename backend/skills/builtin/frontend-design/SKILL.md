---
name: frontend-design
description: UI and interaction quality - responsive design, accessibility, modern CSS, component patterns
triggers: [frontend, ui, ux, responsive, css, accessibility, component, design system]
category: frontend
auto_activate: true
priority: 6
---

# Frontend Design

## UI Principles
1. **Visual hierarchy** — size, color, spacing guide the eye
2. **Consistency** — same patterns for same actions
3. **Feedback** — every user action gets visible response
4. **Progressive disclosure** — show essentials first, details on demand

## Responsive Design
- Mobile-first approach (min-width breakpoints)
- Fluid typography with clamp()
- CSS Grid for layout, Flexbox for alignment
- Test at 320px, 768px, 1024px, 1440px

## Accessibility
- Semantic HTML (nav, main, article, aside)
- Keyboard navigation for all interactive elements
- Sufficient color contrast (WCAG 2.1 AA: 4.5:1)
- Alt text on all images, aria-labels on icons

## Component Architecture
- Small, focused components (< 200 lines)
- Props for configuration, events for communication
- Separate presentational from container components
- Design tokens for colors, spacing, typography

Source: antigravity-awesome-skills
