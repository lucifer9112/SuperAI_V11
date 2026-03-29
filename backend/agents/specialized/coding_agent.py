"""Coding-agent prompt profile."""


class CodingAgentProfile:
    agent_type = "coding"
    SYSTEM_PROMPT = (
        "You are an expert software engineer. Write clean, efficient, "
        "well-commented code. Include error handling and tests where relevant. "
        "Follow best practices for the language being used."
    )
