from core.agent import Agent


def run() -> int:
    """Start the agent and return a process exit code."""
    agent = Agent()
    status = agent.start()

    if not status.ok:
        print(status.message)
        return 1

    try:
        print(status.message)
        return 0
    finally:
        agent.stop()
