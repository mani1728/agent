from dataclasses import dataclass

from agent.adapters.http_transport import HTTPTransportAdapter
from agent.adapters.mt5_adapter import MT5Adapter
from agent.application.app import build_dispatcher
from agent.application.boundary import ApplicationBoundary
from agent.contracts.configuration import AgentConfig
from agent.contracts.ports import AuthenticationPort, AuthorizationPort, MT5Port, ObservabilityPort
from agent.core.agent import Agent


@dataclass(frozen=True)
class AgentComposition:
    config: AgentConfig
    agent: Agent
    application: ApplicationBoundary
    http_transport: HTTPTransportAdapter


def compose_agent(
    config: AgentConfig,
    mt5: MT5Port | None = None,
    authenticator: AuthenticationPort | None = None,
    authorizer: AuthorizationPort | None = None,
    observability: ObservabilityPort | None = None,
) -> AgentComposition:
    """Single composition root for concrete application dependencies."""
    agent = Agent(mt5 or MT5Adapter())
    dispatcher = build_dispatcher(agent)
    application = ApplicationBoundary(dispatcher, authenticator, authorizer, observability)
    transport = HTTPTransportAdapter(application, max_request_bytes=config.http.max_request_bytes)
    return AgentComposition(config, agent, application, transport)
