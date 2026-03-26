---
name: aws-serverless
description: AWS serverless architecture - Lambda, API Gateway, DynamoDB, S3, CloudFormation
triggers: [aws, lambda, serverless, api gateway, dynamodb, s3, cloud, cloudformation, sam]
category: devops
auto_activate: false
priority: 5
---

# AWS Serverless

## Core Services
| Service | Use For |
|---------|---------|
| Lambda | Compute (event-driven functions) |
| API Gateway | HTTP endpoints |
| DynamoDB | NoSQL database |
| S3 | File storage |
| SQS | Message queue |
| EventBridge | Event routing |
| CloudWatch | Monitoring + logging |

## Best Practices
- Keep Lambda functions focused (one function per task)
- Set timeouts (default 3s, max 15min)
- Use environment variables for config
- Enable X-Ray tracing for debugging
- Use Layers for shared dependencies
- Provisioned concurrency for latency-sensitive endpoints

## Cost Optimization
- Right-size memory (more memory = faster execution = fewer ms billed)
- Use reserved concurrency to prevent runaway costs
- S3 lifecycle policies for old data
- DynamoDB on-demand for unpredictable traffic

Source: antigravity-awesome-skills
