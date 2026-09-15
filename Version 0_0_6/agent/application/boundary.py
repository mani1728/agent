from uuid import uuid4

from agent.application.dispatcher import CommandDispatcher
from agent.contracts.models import Command
from agent.contracts.observability import ExecutionEvent, ExecutionEventType, NullObservability
from agent.contracts.ports import ApplicationPort
from agent.contracts.security import AllowAllAuthenticator, AllowAllAuthorizer, Authenticator, Authorizer, AuthenticationResult
from agent.contracts.transport import TransportRequest, TransportResponse, TransportValidationError, validate_transport_request


class ApplicationBoundary(ApplicationPort):
    """Transport-neutral ingress; security ordering is validation -> auth -> authz -> dispatch."""

    def __init__(self, dispatcher: CommandDispatcher, authenticator: Authenticator | None = None,
                 authorizer: Authorizer | None = None, observability: object | None = None) -> None:
        self._dispatcher = dispatcher
        self._authenticator = authenticator or AllowAllAuthenticator()
        self._authorizer = authorizer or AllowAllAuthorizer()
        self._observability = observability or NullObservability()

    def _record(self, event: ExecutionEvent) -> None:
        try:
            self._observability.record(event)
        except Exception:
            return None

    @staticmethod
    def _event(request: TransportRequest | None, event_type: ExecutionEventType, outcome: str, command_id: str = "") -> ExecutionEvent:
        context = request.context if isinstance(request, TransportRequest) else None
        return ExecutionEvent.now(str(uuid4()), event_type, context.request_id if context else "unknown",
                                  context.correlation_id if context else "unknown", command_id, outcome)

    @staticmethod
    def _response(request: TransportRequest | None, command: Command | None, success: bool,
                  code: str, message: str = "", data=None) -> TransportResponse:
        return TransportResponse(request.context.request_id if isinstance(request, TransportRequest) else "",
                                 request.context.correlation_id if isinstance(request, TransportRequest) else "",
                                 command.command_id if isinstance(command, Command) else "", success, code, message, data)

    def handle(self, request: TransportRequest) -> TransportResponse:
        self._record(self._event(request, ExecutionEventType.REQUEST_RECEIVED, "received"))
        try:
            validate_transport_request(request)
        except TransportValidationError as exc:
            self._record(self._event(request, ExecutionEventType.REQUEST_REJECTED, "invalid_request"))
            return self._response(request, request.command if isinstance(request, TransportRequest) else None, False, "invalid_request", str(exc))

        command = request.command
        try:
            auth_result: AuthenticationResult = self._authenticator.authenticate(request)
        except Exception:
            self._record(self._event(request, ExecutionEventType.AUTHENTICATION_COMPLETED, "failed", command.command_id))
            return self._response(request, command, False, "authentication_failed", "Authentication failed.")
        self._record(self._event(request, ExecutionEventType.AUTHENTICATION_COMPLETED,
                                 "success" if auth_result.success else "failed", command.command_id))
        if not auth_result.success or auth_result.context is None:
            return self._response(request, command, False, auth_result.code or "authentication_failed", auth_result.message)

        try:
            decision = self._authorizer.authorize(auth_result.context, command)
        except Exception:
            self._record(self._event(request, ExecutionEventType.AUTHORIZATION_COMPLETED, "failed", command.command_id))
            return self._response(request, command, False, "authorization_failed", "Authorization failed.")
        self._record(self._event(request, ExecutionEventType.AUTHORIZATION_COMPLETED,
                                 "allowed" if decision.allowed else "denied", command.command_id))
        if not decision.allowed:
            return self._response(request, command, False, decision.code or "authorization_denied", decision.message)

        self._record(self._event(request, ExecutionEventType.COMMAND_DISPATCHED, "started", command.command_id))
        result = self._dispatcher.dispatch(command)
        response = self._response(request, command, result.success, result.code, result.message, result.data)
        self._record(self._event(request, ExecutionEventType.REQUEST_COMPLETED, result.code, command.command_id))
        return response
