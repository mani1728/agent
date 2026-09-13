from agent.contracts.models import Status
from agent.core.agent import Agent


def check(agent: Agent) -> Status:
    """Return the current readiness status of the agent."""
    return agent.is_ready()
