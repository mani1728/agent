from agent.contracts.models import HealthStatus
from agent.core.agent import Agent


def check(agent: Agent) -> HealthStatus:
    """Return the structured runtime health status."""
    return agent.health()
