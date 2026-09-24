from agent.application.dispatcher import CommandDispatcher
from agent.contracts.models import Command
from agent.contracts.protocol import CapabilityClass, CommandDefinition, CommandRegistry, ProtocolVersion


def command(name="agent.read", version="1"):
    return Command("cmd-1", name, version, "corr-1", "2026-09-24T00:00:00+00:00", {})


def test_protocol_version_and_manifest_are_deterministic():
    registry = CommandRegistry(ProtocolVersion("1"))
    registry.register(CommandDefinition(
        "agent.z", "1", CapabilityClass.READ, lambda _: None))
    registry.register(CommandDefinition(
        "agent.a", "2", CapabilityClass.TRADE_ANALYSIS, lambda _: None))
    assert registry.manifest("0.1.3").to_dict() == {
        "agent_version": "0.1.3", "protocol_version": "1",
        "commands": [
            {"identifier": "agent.a", "version": "2", "capability_class": "trade_analysis", "enabled": True},
            {"identifier": "agent.z", "version": "1", "capability_class": "read", "enabled": True},
        ],
    }


def test_duplicate_registration_is_rejected_and_no_dynamic_dispatch_exists():
    dispatcher = CommandDispatcher()
    dispatcher.register("agent.read", lambda _: {"safe": True})
    try:
        dispatcher.register("agent.read", lambda _: None)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate registration was accepted")
    assert dispatcher.dispatch(command("os.system")).code == "UNSUPPORTED_COMMAND"


def test_version_and_class_or_command_disable_fail_closed():
    registry = CommandRegistry()
    dispatcher = CommandDispatcher(registry=registry)
    dispatcher.register("agent.read", lambda _: {"ok": True}, capability_class=CapabilityClass.READ)
    assert dispatcher.dispatch(command(version="2")).code == "UNSUPPORTED_COMMAND_VERSION"
    registry.set_class_enabled(CapabilityClass.READ, False)
    assert dispatcher.dispatch(command()).code == "CAPABILITY_DISABLED"
    registry.set_class_enabled(CapabilityClass.READ, True)
    registry.set_command_enabled("agent.read", False)
    assert dispatcher.dispatch(command()).code == "COMMAND_DISABLED"
