from dataclasses import dataclass

from agent.adapters.http_transport import HTTPTransportAdapter
from agent.adapters.mt5_adapter import MT5Adapter
from agent.application.app import build_dispatcher
from agent.application.boundary import ApplicationBoundary
from agent.application.dispatcher import CommandDispatcher
from agent.application.host import ApplicationHost
from agent.application.registry.capability import InMemoryCapabilityRegistry
from agent.contracts.configuration import AgentConfig
from agent.contracts.operational_observability import OperationalObservabilityPort
from agent.contracts.ports import AuthenticationPort, AuthorizationPort, HostingPort, MT5Port, ObservabilityPort
from agent.core.agent import Agent
from agent.infrastructure.http_server_host import HTTPServerHost


@dataclass(frozen=True)
class AgentComposition:
    config: AgentConfig
    agent: Agent
    dispatcher: CommandDispatcher
    application: ApplicationBoundary
    http_transport: HTTPTransportAdapter
    hosting: HostingPort
    host: ApplicationHost


def compose_agent(
    config: AgentConfig,
    mt5: MT5Port | None = None,
    authenticator: AuthenticationPort | None = None,
    authorizer: AuthorizationPort | None = None,
    observability: ObservabilityPort | None = None,
    hosting: HostingPort | None = None,
    operational_observability: OperationalObservabilityPort | None = None,
) -> AgentComposition:
    """Single composition root for concrete application dependencies."""
    agent = Agent(mt5 or MT5Adapter())

    capability_registry = InMemoryCapabilityRegistry([])
    dispatcher = build_dispatcher(agent, capability_provider=capability_registry)

    application = ApplicationBoundary(dispatcher, authenticator, authorizer, observability)
    transport = HTTPTransportAdapter(application, max_request_bytes=config.http.max_request_bytes)
    concrete_hosting = hosting or HTTPServerHost(
        lambda: transport.create_server(config.http.host, config.http.port)
    )
    host = ApplicationHost(
        agent,
        concrete_hosting,
        operational_observability=operational_observability,
    )
    return AgentComposition(config, agent, dispatcher, application, transport, concrete_hosting, host)
