import logging

from agent.adapters.mt5_adapter import MT5Adapter
from agent.core.agent import Agent


def run() -> int:
    """Run one synchronous lifecycle and return a process exit code."""
    logging.basicConfig(level=logging.INFO)
    agent = Agent(MT5Adapter())

    try:
        status = agent.start()
        print(status.message)
        return 0 if status.ok else 1
    finally:
        stop_status = agent.stop()
        if not stop_status.ok:
            logging.getLogger(__name__).error(stop_status.message)
