import json
from datetime import datetime, timezone

from agent.adapters.http_transport import HTTPTransportAdapter
from agent.application.boundary import ApplicationBoundary
from agent.application.dispatcher import CommandDispatcher
from agent.contracts.models import CommandResult
from agent.contracts.security import AuthenticationResult, AuthorizationDecision, SecurityContext
from agent.contracts.transport import TransportResponse


def payload(command_id="cmd-1", correlation_id="corr-1", command_type="agent.get_status"):
    return {
        "request_id": "req-1",
        "correlation_id": correlation_id,
        "command": {
            "command_id": command_id,
            "command_type": command_type,
            "schema_version": "1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {},
        },
    }


def test_valid_request_reaches_application_and_preserves_identity():
    seen = []

    class App:
        def handle(self, request):
            seen.append(request)
            return TransportResponse("req-1", "corr-1", "cmd-1", True, "ok", "done", {"x": 1})

    response = HTTPTransportAdapter(App()).handle_json(json.dumps(payload()).encode())
    assert response.status == 200
    body = json.loads(response.body)
    assert body["request_id"] == "req-1"
    assert body["correlation_id"] == "corr-1"
    assert body["command_id"] == "cmd-1"
    assert seen[0].context.request_id == "req-1"
    assert seen[0].context.correlation_id == "corr-1"
    assert seen[0].command.command_id == "cmd-1"


def test_missing_request_id_is_rejected_without_application_call():
    value = payload()
    del value["request_id"]
    calls = []

    class App:
        def handle(self, request):
            calls.append(request)
            raise AssertionError("must not be called")

    response = HTTPTransportAdapter(App()).handle_json(json.dumps(value).encode())
    assert response.status == 400
    assert json.loads(response.body)["code"] == "invalid_request"
    assert calls == []


def test_malformed_json_is_transport_error():
    response = HTTPTransportAdapter(lambda request: None).handle_json(b"{")
    assert response.status == 400
    assert json.loads(response.body)["code"] == "invalid_request"


def test_non_object_json_is_rejected():
    response = HTTPTransportAdapter(lambda request: None).handle_json(b"[]")
    assert response.status == 400


def test_correlation_mismatch_is_rejected():
    value = payload(correlation_id="corr-body")
    value["command"]["correlation_id"] = "corr-command"
    response = HTTPTransportAdapter(lambda request: None).handle_json(json.dumps(value).encode())
    assert response.status == 400
    assert json.loads(response.body)["code"] == "invalid_request"


def test_application_failure_is_sanitized():
    class App:
        def handle(self, request):
            raise RuntimeError("secret internal detail")

    response = HTTPTransportAdapter(App()).handle_json(json.dumps(payload()).encode())
    body = json.loads(response.body)
    assert response.status == 500
    assert body["code"] == "application_error"
    assert body["message"] == "Application request failed."
    assert "secret internal detail" not in response.body.decode()


def test_application_error_result_maps_deterministically():
    class App:
        def handle(self, request):
            return TransportResponse("req-1", "corr-1", "cmd-1", False, "unknown_command", "Unknown command type: x")

    response = HTTPTransportAdapter(App()).handle_json(json.dumps(payload()).encode())
    assert response.status == 404
    assert json.loads(response.body)["code"] == "unknown_command"


def test_response_serialization_failure_is_transport_error():
    class App:
        def handle(self, request):
            return TransportResponse("req-1", "corr-1", "cmd-1", True, "ok", "done", object())

    response = HTTPTransportAdapter(App()).handle_json(json.dumps(payload()).encode())
    body = json.loads(response.body)
    assert response.status == 500
    assert body["code"] == "transport_error"
    assert body["message"] == "Response serialization failed."


def test_application_boundary_authentication_precedes_authorization_and_dispatch():
    order = []
    dispatcher = CommandDispatcher()
    dispatcher.register("agent.get_status", lambda command: order.append("dispatch") or {"ok": True})

    class Auth:
        def authenticate(self, request):
            order.append("authenticate")
            return AuthenticationResult(True, SecurityContext("user", "test", frozenset(), {}))

    class Authz:
        def authorize(self, context, command):
            order.append("authorize")
            return AuthorizationDecision(True)

    app = ApplicationBoundary(dispatcher, Auth(), Authz())
    response = HTTPTransportAdapter(app).handle_json(json.dumps(payload()).encode())
    assert response.status == 200
    assert order == ["authenticate", "authorize", "dispatch"]


def test_unauthorized_request_never_reaches_dispatcher():
    calls = []
    dispatcher = CommandDispatcher()
    dispatcher.register("agent.get_status", lambda command: calls.append(command))

    class Authz:
        def authorize(self, context, command):
            return AuthorizationDecision(False, "authorization_denied", "Denied.")

    app = ApplicationBoundary(dispatcher, authorizer=Authz())
    response = HTTPTransportAdapter(app).handle_json(json.dumps(payload()).encode())
    assert response.status == 403
    assert calls == []


def test_authentication_failure_never_reaches_authorization_or_dispatch():
    order = []
    dispatcher = CommandDispatcher()
    dispatcher.register("agent.get_status", lambda command: order.append("dispatch"))

    class Auth:
        def authenticate(self, request):
            order.append("authenticate")
            return AuthenticationResult(False, None, "authentication_failed", "No identity.")

    class Authz:
        def authorize(self, context, command):
            order.append("authorize")
            return AuthorizationDecision(True)

    app = ApplicationBoundary(dispatcher, Auth(), Authz())
    response = HTTPTransportAdapter(app).handle_json(json.dumps(payload()).encode())
    assert response.status == 401
    assert order == ["authenticate"]


def test_observer_failure_does_not_fail_valid_execution():
    dispatcher = CommandDispatcher()
    dispatcher.register("agent.get_status", lambda command: {"ok": True})

    class Observer:
        def record(self, event):
            raise RuntimeError("observer unavailable")

    app = ApplicationBoundary(dispatcher, observability=Observer())
    response = HTTPTransportAdapter(app).handle_json(json.dumps(payload()).encode())
    assert response.status == 200
    assert json.loads(response.body)["success"] is True


def test_invalid_command_is_mapped_as_application_error():
    dispatcher = CommandDispatcher()
    app = ApplicationBoundary(dispatcher)
    value = payload(command_type="does.not.exist")
    response = HTTPTransportAdapter(app).handle_json(json.dumps(value).encode())
    body = json.loads(response.body)
    assert response.status == 404
    assert body["code"] == "unknown_command"


def test_invalid_command_schema_is_mapped_as_bad_request():
    dispatcher = CommandDispatcher()
    dispatcher.register("agent.get_status", lambda command: {})
    app = ApplicationBoundary(dispatcher)
    value = payload()
    value["command"]["schema_version"] = "999"
    response = HTTPTransportAdapter(app).handle_json(json.dumps(value).encode())
    assert response.status == 400
    assert json.loads(response.body)["code"] == "unsupported_schema"


def test_http_server_exposes_only_command_post():
    dispatcher = CommandDispatcher()
    app = ApplicationBoundary(dispatcher)
    server = HTTPTransportAdapter(app).create_server(port=0)
    try:
        assert server.server_address[1] > 0
    finally:
        server.server_close()
