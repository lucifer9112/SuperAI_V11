---
name: vercel-deployment
description: Vercel deployment best practices - Next.js, edge functions, environment config
triggers: [vercel, deploy, next.js, edge, serverless, preview, production, hosting]
category: devops
auto_activate: false
priority: 4
---

# Vercel Deployment

## Setup
- `vercel.json` for custom configuration
- Link to Git repo for automatic deploys
- Preview deployments on every PR
- Environment variables per environment (dev/preview/prod)

## Next.js Optimization
- Use `output: 'standalone'` for smaller Docker images
- ISR (Incremental Static Regeneration) for dynamic content
- Edge functions for low-latency APIs
- Image optimization with next/image

## Performance
- Enable caching headers on static assets
- Use Edge Config for feature flags
- Serverless function regions close to users
- Monitor with Vercel Analytics

Source: antigravity-awesome-skills
