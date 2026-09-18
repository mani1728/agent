from agent.application.dispatcher import CommandDispatcher
from agent.contracts.models import Command
from agent.application.ports.capability import CapabilityProviderPort

GET_STATUS = "agent.get_status"
GET_HEALTH = "agent.get_health"


def build_dispatcher(
    agent,
    capability_provider: CapabilityProviderPort | None = None,
) -> CommandDispatcher:
    dispatcher = CommandDispatcher()

    def status_handler(command: Command):
        return {"state": agent.state.value, "version": agent.identity.version, "app_name": agent.identity.app_name}

    def health_handler(command: Command):
        health = agent.health()
        return {"ok": health.ok, "state": health.state.value, "message": health.message}

    dispatcher.register(GET_STATUS, status_handler)
    dispatcher.register(GET_HEALTH, health_handler)

    if capability_provider is not None:
        dispatcher.register_capability_handlers(capability_provider)

    return dispatcher
