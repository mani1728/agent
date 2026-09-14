import logging

from agent.application.app import GET_STATUS, build_dispatcher
from agent.application.boundary import ApplicationBoundary
from agent.contracts.commands import make_command
from agent.contracts.models import AgentConfig
from agent.contracts.ports import ApplicationPort
from agent.contracts.transport import (
    ExecutionContext,
    TransportRequest,
    TransportValidationError,
    validate_execution_context,
    validate_transport_request,
)
from agent.core.agent import Agent


class FakeMT5:
    def connect(self):
        return True

    def disconnect(self):
        return True

    def is_connected(self):
        return True


def request(command_id="cmd-1", correlation_id="corr-1", request_id="req-1"):
    command = make_command(command_id, GET_STATUS, correlation_id, {}, "2026-09-14T10:00:00+00:00")
    context = ExecutionContext(request_id, correlation_id, {"source": "test"})
    return TransportRequest(context, command)


def test_execution_context_normalizes_metadata_to_immutable_mapping():
    metadata = {"source": "test"}
    context = ExecutionContext("req-1", "corr-1", metadata)
    metadata["source"] = "changed"
    assert context.metadata["source"] == "test"
    try:
        context.metadata["new"] = "value"
        assert False, "metadata must be immutable"
    except TypeError:
        pass


def test_transport_request_preserves_identity_and_dispatches():
    agent = Agent(FakeMT5(), AgentConfig(), logging.getLogger("test"))
    application = ApplicationBoundary(build_dispatcher(agent))
    result = application.handle(request())
    assert result.success is True
    assert result.code == "ok"
    assert result.request_id == "req-1"
    assert result.command_id == "cmd-1"
    assert result.correlation_id == "corr-1"


def test_application_port_is_transport_neutral():
    agent = Agent(FakeMT5(), AgentConfig(), logging.getLogger("test"))
    application = ApplicationBoundary(build_dispatcher(agent))
    assert isinstance(application, ApplicationPort)


def test_correlation_mismatch_is_rejected_at_request_boundary():
    command = make_command("cmd-1", GET_STATUS, "command-corr", {}, "2026-09-14T10:00:00+00:00")
    context = ExecutionContext("req-1", "request-corr", {})
    request_value = TransportRequest(context, command)
    try:
        validate_transport_request(request_value)
        assert False, "correlation mismatch must be rejected"
    except TransportValidationError as exc:
        assert "correlation_id" in str(exc)


def test_application_boundary_returns_deterministic_invalid_request():
    agent = Agent(FakeMT5(), AgentConfig(), logging.getLogger("test"))
    application = ApplicationBoundary(build_dispatcher(agent))
    command = make_command("cmd-1", GET_STATUS, "command-corr", {}, "2026-09-14T10:00:00+00:00")
    invalid_request = TransportRequest(ExecutionContext("req-1", "request-corr", {}), command)
    result = application.handle(invalid_request)
    assert result.success is False
    assert result.code == "invalid_request"
    assert result.request_id == "req-1"
    assert result.command_id == "cmd-1"


def test_context_validation_requires_identifiers():
    try:
        validate_execution_context(ExecutionContext("", "corr-1", {}))
        assert False, "empty request_id must be rejected"
    except TransportValidationError:
        pass
