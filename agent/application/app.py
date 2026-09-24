from agent.application.dispatcher import CommandDispatcher
from agent.contracts.models import Command
from agent.application.ports.capability import CapabilityProviderPort
from agent.contracts.protocol import CapabilityClass

GET_STATUS = "agent.get_status"
GET_HEALTH = "agent.get_health"


def build_dispatcher(
    agent,
    capability_provider: CapabilityProviderPort | None = None,
    mt5_read_adapter=None,
) -> CommandDispatcher:
    dispatcher = CommandDispatcher()

    def status_handler(command: Command):
        return {"state": agent.state.value, "version": agent.identity.version, "app_name": agent.identity.app_name}

    def health_handler(command: Command):
        health = agent.health()
        return {"ok": health.ok, "state": health.state.value, "message": health.message}

    dispatcher.register(GET_STATUS, status_handler, capability_class=CapabilityClass.READ)
    dispatcher.register(GET_HEALTH, health_handler, capability_class=CapabilityClass.READ)
    if mt5_read_adapter is not None:
        from agent.application.mt5_read_commands import build_mt5_read_handlers
        for name, handler in build_mt5_read_handlers(mt5_read_adapter).items():
            dispatcher.register(name, handler, capability_class=CapabilityClass.READ)

    if capability_provider is not None:
        dispatcher.register_capability_handlers(capability_provider)

        def capability_manifest(_command: Command):
            return dispatcher.capability_manifest(agent.identity.version).to_dict()

        dispatcher.register("agent.get_capability_manifest", capability_manifest,
                            capability_class=CapabilityClass.READ)

    return dispatcher
