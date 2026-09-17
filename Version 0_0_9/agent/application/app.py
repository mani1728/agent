from agent.application.dispatcher import CommandDispatcher
from agent.contracts.models import Command
from agent.application.registry.capability import InMemoryCapabilityRegistry
from agent.application.ports.capability import CapabilityProviderPort

GET_STATUS = "agent.get_status"
GET_HEALTH = "agent.get_health"


def build_dispatcher(
    agent,
    capability_provider: CapabilityProviderPort | None = None,
) -> CommandDispatcher:
    dispatcher = CommandDispatcher()

    def status_handler(command: Command):
        return {"state": agent.state.value, "version": agent.config.version, "app_name": agent.config.app_name}

    def health_handler(command: Command):
        health = agent.health()
        return {"ok": health.ok, "state": health.state.value, "message": health.message}

    def capabilities_handler(command: Command):
        return {
            "capabilities": [item.to_dict() for item in capability_provider.get_capabilities()]
        }

    def runtime_info_handler(command: Command):
        return capability_provider.get_runtime_information().to_dict()

    dispatcher.register(GET_STATUS, status_handler)
    dispatcher.register(GET_HEALTH, health_handler)

    if capability_provider is not None:
        dispatcher.register("agent.get_capabilities", capabilities_handler)
        dispatcher.register("agent.get_runtime_info", runtime_info_handler)

    return dispatcher
