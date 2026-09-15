import logging

from agent.composition import compose_agent
from agent.contracts.commands import make_command
from agent.contracts.configuration import ConfigurationError
from agent.infrastructure.environment_config import EnvironmentConfigurationProvider


def run() -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        config = EnvironmentConfigurationProvider().load()
        composition = compose_agent(config)
    except ConfigurationError as exc:
        logging.getLogger(__name__).error("Invalid startup configuration: %s", exc)
        return 2

    agent = composition.agent
    try:
        status = agent.start()
        if status.ok:
            result = composition.dispatcher.dispatch(
                make_command("startup-status", "agent.get_status", "startup-status")
            )
            print(result.message)
        else:
            print(status.message)
        return 0 if status.ok else 1
    finally:
        stop_status = agent.stop()
        if not stop_status.ok:
            logging.getLogger(__name__).error(stop_status.message)
