from agent.contracts.models import HealthStatus
from agent.core.agent import Agent


def check(agent: Agent) -> HealthStatus:
    return agent.health()
