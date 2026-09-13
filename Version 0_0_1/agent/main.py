from agent.core.agent import Agent


def run() -> int:
    """Start the agent and return a process exit code."""
    agent = Agent()

    if not agent.start():
        return 1

    try:
        print("Agent started successfully.")
        return 0
    finally:
        agent.stop()
