import logging

from agent.core.agent import Agent


def run() -> int:
    """Run one synchronous lifecycle and return a process exit code."""
    logging.basicConfig(level=logging.INFO)
    agent = Agent()
    status = agent.start()
    print(status.message)

    if not status.ok:
        return 1

    try:
        return 0
    finally:
        agent.stop()
