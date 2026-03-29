"""Reusable specialized-agent prompt profiles for the parallel executor."""

from backend.agents.specialized.coding_agent import CodingAgentProfile
from backend.agents.specialized.planning_agent import PlanningAgentProfile
from backend.agents.specialized.reasoning_agent import ReasoningAgentProfile
from backend.agents.specialized.research_agent import ResearchAgentProfile

__all__ = [
    "CodingAgentProfile",
    "PlanningAgentProfile",
    "ReasoningAgentProfile",
    "ResearchAgentProfile",
]
