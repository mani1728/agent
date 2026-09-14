import logging

from agent.application.boundary import ApplicationBoundary
from agent.application.app import build_dispatcher
from agent.contracts.commands import make_command
from agent.contracts.models import AgentConfig
from agent.contracts.observability import ExecutionEventType
from agent.contracts.security import AuthenticationResult, AuthorizationDecision, SecurityContext
from agent.contracts.transport import ExecutionContext, TransportRequest
from agent.core.agent import Agent


class FakeMT5:
    def connect(self):
        return True

    def disconnect(self):
        return True

    def is_connected(self):
        return True


class RecordingObserver:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


class FakeAuthenticator:
    def __init__(self, result):
        self.result = result

    def authenticate(self, request):
        return self.result


class FakeAuthorizer:
    def __init__(self, decision):
        self.decision = decision

    def authorize(self, context, command):
        return self.decision


def request():
    command = make_command("cmd-1", "agent.get_status", "corr-1", {}, "2026-09-15T10:00:00+00:00")
    return TransportRequest(ExecutionContext("req-1", "corr-1", {}), command)


def application(authenticator=None, authorizer=None, observer=None):
    agent = Agent(FakeMT5(), AgentConfig(), logging.getLogger("test"))
    return ApplicationBoundary(
        build_dispatcher(agent),
        authenticator=authenticator,
        authorizer=authorizer,
        observability=observer,
    )


def authenticated():
    return AuthenticationResult(
        True,
        SecurityContext("principal-1", "test", frozenset({"agent.read"}), {}),
    )


def test_security_context_is_immutable_and_normalized():
    context = authenticated().context
    assert context.permissions == frozenset({"agent.read"})
    assert context.metadata == {}
    try:
        context.permissions = frozenset()
        raise AssertionError("SecurityContext must be immutable")
    except AttributeError:
        pass


def test_authentication_failure_is_deterministic():
    result = AuthenticationResult(False, code="authentication_failed", message="invalid credential")
    response = application(FakeAuthenticator(result)).handle(request())
    assert response.success is False
    assert response.code == "authentication_failed"


def test_authorization_denial_blocks_dispatch():
    decision = AuthorizationDecision(False, code="authorization_denied", message="permission missing")
    response = application(FakeAuthenticator(authenticated()), FakeAuthorizer(decision)).handle(request())
    assert response.success is False
    assert response.code == "authorization_denied"


def test_authorization_exception_is_translated():
    class FailingAuthorizer:
        def authorize(self, context, command):
            raise RuntimeError("policy backend unavailable")

    response = application(FakeAuthenticator(authenticated()), FailingAuthorizer()).handle(request())
    assert response.success is False
    assert response.code == "authorization_failed"


def test_successful_request_emits_execution_events():
    observer = RecordingObserver()
    response = application(FakeAuthenticator(authenticated()), FakeAuthorizer(AuthorizationDecision(True)), observer).handle(request())
    assert response.success is True
    assert [event.event_type for event in observer.events] == [
        ExecutionEventType.REQUEST_RECEIVED,
        ExecutionEventType.AUTHENTICATION_COMPLETED,
        ExecutionEventType.AUTHORIZATION_COMPLETED,
        ExecutionEventType.COMMAND_DISPATCHED,
        ExecutionEventType.REQUEST_COMPLETED,
    ]
    assert all(event.request_id == "req-1" for event in observer.events)
    assert all(event.correlation_id == "corr-1" for event in observer.events)


def test_invalid_request_is_rejected_before_authentication():
    observer = RecordingObserver()
    command = make_command("cmd-1", "agent.get_status", "command-corr", {}, "2026-09-15T10:00:00+00:00")
    invalid = TransportRequest(ExecutionContext("req-1", "request-corr", {}), command)
    response = application(FakeAuthenticator(authenticated()), observer=observer).handle(invalid)
    assert response.success is False
    assert response.code == "invalid_request"
    assert [event.event_type for event in observer.events] == [
        ExecutionEventType.REQUEST_RECEIVED,
        ExecutionEventType.REQUEST_REJECTED,
    ]


def test_observability_failure_does_not_break_execution():
    class BrokenObserver:
        def record(self, event):
            raise RuntimeError("telemetry unavailable")

    response = application(FakeAuthenticator(authenticated()), FakeAuthorizer(AuthorizationDecision(True)), BrokenObserver()).handle(request())
    assert response.success is True


def test_authentication_exception_is_translated():
    class FailingAuthenticator:
        def authenticate(self, request):
            raise RuntimeError("credential provider unavailable")

    response = application(FailingAuthenticator()).handle(request())
    assert response.success is False
    assert response.code == "authentication_failed"
