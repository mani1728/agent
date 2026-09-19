import argparse
import json
import logging
import sys

from agent import __version__
from agent.contracts.configuration import ConfigurationError, LoggingConfig
from agent.infrastructure.environment_config import EnvironmentConfigurationProvider
from agent.infrastructure.logging_observability import configure_logging, safe_log


def run(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MT5 Agent runtime and inspection-only self-check")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--version", action="store_true", help="Print version without initializing MT5")
    modes.add_argument("--diagnose", action="store_true", help="Inspect readiness without starting MT5 or HTTP")
    parser.add_argument("--json", action="store_true", help="Machine-readable diagnostic output")
    args = parser.parse_args(argv)
    if args.json and not args.diagnose:
        parser.error("--json requires --diagnose")
    if args.version:
        print(__version__)
        return 0
    if args.diagnose:
        from agent.application.diagnostics import diagnose
        from agent.infrastructure.terminal_inspection import inspect_terminal
        result = diagnose(EnvironmentConfigurationProvider(), inspect_terminal)
        if args.json:
            print(json.dumps(result, ensure_ascii=True))
        else:
            print(f"{result['app_name']} {result['agent_version']}")
            print(f"Configuration valid: {result['configuration']['valid']}")
            print(f"HTTP: {result['configuration']['http_host']}:{result['configuration']['http_port']}")
            if "error" in result["configuration"]:
                print(result["configuration"]["error"])
            print(f"MT5 dependency available: {result['terminal']['dependency_available']}")
            print(f"Terminal process running: {result['terminal']['process_running']}")
            print("Terminal paths: " + (", ".join(result['terminal']['paths']) or "not discovered"))
            print("Inspection errors: " + (", ".join(result['terminal']['errors']) or "none"))
            print(f"Ready: {result['ready']}")
            print(result["limitations"])
        return 0 if result["ready"] else 1

    try:
        config = EnvironmentConfigurationProvider().load()
    except ConfigurationError as exc:
        logger = configure_logging(LoggingConfig())
        safe_log(logger, logging.ERROR, "Invalid startup configuration: %s", exc)
        return 2
    logger = configure_logging(config.logging)
    safe_log(logger, logging.INFO, "MT5 Agent %s starting", __version__)
    safe_log(logger, logging.INFO, "Configuration loaded and validated")
    safe_log(logger, logging.DEBUG, "Python runtime %s.%s; HTTP request limit %s bytes",
             sys.version_info.major, sys.version_info.minor, config.http.max_request_bytes)
    # Lazy composition ensures --version works even if the MT5 dependency is absent.
    from agent.composition import compose_agent
    from agent.infrastructure.process_signals import install_shutdown_signal_handlers
    composition = compose_agent(config)
    install_shutdown_signal_handlers(composition.hosting.shutdown)
    status = composition.host.run()
    if status.ok:
        return 0  # Production lifecycle observer already logged successful shutdown.
    safe_log(logger, logging.ERROR, "%s (%s)", status.message, status.code)
    return 1
