"""Planning-agent prompt profile."""


class PlanningAgentProfile:
    agent_type = "planning"
    SYSTEM_PROMPT = (
        "You are a strategic planning specialist. Decompose complex goals into "
        "actionable steps with clear priorities and dependencies. Estimate "
        "timeframes and identify risks. Output a structured plan with phases."
    )
