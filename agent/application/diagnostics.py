"""Application self-check, separate from long-running host composition."""
from agent.contracts.configuration import ConfigurationError
from agent.contracts.models import AgentIdentity


def diagnose(config_provider, inspect):
    identity = AgentIdentity()
    configuration = {"valid": False, "http_host": None, "http_port": None}
    try:
        config = config_provider.load()
        configuration.update(valid=True, http_host=config.http.host, http_port=config.http.port)
    except ConfigurationError as exc:
        # Configuration errors contain fixed messages, never rejected raw values.
        configuration["error"] = str(exc)
    try:
        terminal = inspect().to_dict()
    except Exception:
        terminal = {"supported": False, "paths": [], "process_running": None,
                    "dependency_available": False, "errors": ["inspection_failed"],
                    "searched_locations": []}
    ready = (configuration["valid"] and terminal["supported"] and terminal["dependency_available"]
             and bool(terminal["paths"]) and terminal["process_running"] is not None and not terminal["errors"])
    return {
        "schema_version": "1", "agent_version": identity.version, "app_name": identity.app_name,
        "configuration": configuration, "terminal": terminal, "ready": bool(ready),
        "inspection_only": True,
        "limitations": "Bounded discovery; unlisted portable installations may be missed. "
                       "Readiness does not prove MT5 connectivity, login or HTTP port availability.",
    }
