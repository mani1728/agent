import logging

from agent.adapters.mt5_adapter import MT5Adapter
from agent.application.app import build_dispatcher
from agent.contracts.commands import make_command
from agent.core.agent import Agent


def run() -> int:
    logging.basicConfig(level=logging.INFO)
    agent = Agent(MT5Adapter())
    dispatcher = build_dispatcher(agent)
    try:
        status = agent.start()
        if status.ok:
            result = dispatcher.dispatch(make_command("startup-status", "agent.get_status", "startup-status"))
            print(result.message)
        else:
            print(status.message)
        return 0 if status.ok else 1
    finally:
        stop_status = agent.stop()
        if not stop_status.ok:
            logging.getLogger(__name__).error(stop_status.message)
