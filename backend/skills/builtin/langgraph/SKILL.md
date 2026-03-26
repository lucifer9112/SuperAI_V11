---
name: langgraph
description: LangGraph agent orchestration - state machines, tool calling, multi-agent workflows
triggers: [langgraph, langchain, agent, state machine, tool call, orchestration, graph]
category: ai-ml
auto_activate: false
priority: 5
---

# LangGraph Patterns

## Core Concepts
- **StateGraph** — define agent flow as a directed graph
- **Nodes** — functions that process state
- **Edges** — conditional routing between nodes
- **Checkpointing** — persist state for resumability

## Graph Pattern
```python
graph = StateGraph(AgentState)
graph.add_node("research", research_node)
graph.add_node("write", write_node)
graph.add_node("review", review_node)
graph.add_edge("research", "write")
graph.add_conditional_edges("review",
    decide_next, {"revise": "write", "done": END})
```

## Tool Calling
- Define tools with clear descriptions
- Return structured results (not free text)
- Handle tool errors gracefully
- Set max iterations to prevent loops

## Multi-Agent
- Supervisor pattern for orchestration
- Handoff protocol for agent switching
- Shared state for cross-agent context

Source: antigravity-awesome-skills
