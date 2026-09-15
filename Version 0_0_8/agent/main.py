import logging

from agent.composition import compose_agent
from agent.contracts.configuration import ConfigurationError
from agent.infrastructure.environment_config import EnvironmentConfigurationProvider
from agent.infrastructure.process_signals import install_shutdown_signal_handlers


def run() -> int:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    try:
        config = EnvironmentConfigurationProvider().load()
        composition = compose_agent(config)
    except ConfigurationError as exc:
        logger.error("Invalid startup configuration: %s", exc)
        return 2

    install_shutdown_signal_handlers(composition.hosting.shutdown)
    status = composition.host.run()
    if status.ok:
        logger.info(status.message)
        return 0
    logger.error("%s (%s)", status.message, status.code)
    return 1
