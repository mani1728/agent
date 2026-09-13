from agent.core.agent import Agent


def check(agent: Agent) -> bool:
    """Return True when the agent is ready to operate."""
    return agent.is_ready()
