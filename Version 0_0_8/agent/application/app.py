from agent.application.dispatcher import CommandDispatcher
from agent.contracts.models import Command

GET_STATUS = "agent.get_status"
GET_HEALTH = "agent.get_health"


def build_dispatcher(agent) -> CommandDispatcher:
    dispatcher = CommandDispatcher()

    def status_handler(command: Command):
        return {"state": agent.state.value, "version": agent.config.version, "app_name": agent.config.app_name}

    def health_handler(command: Command):
        health = agent.health()
        return {"ok": health.ok, "state": health.state.value, "message": health.message}

    dispatcher.register(GET_STATUS, status_handler)
    dispatcher.register(GET_HEALTH, health_handler)
    return dispatcher
