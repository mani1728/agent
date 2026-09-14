from uuid import uuid4

from agent.application.dispatcher import CommandDispatcher
from agent.contracts.models import Command
from agent.contracts.observability import ExecutionEvent, ExecutionEventType, NullObservability
from agent.contracts.ports import ApplicationPort
from agent.contracts.security import (
    AllowAllAuthenticator,
    AllowAllAuthorizer,
    Authenticator,
    Authorizer,
    AuthenticationResult,
)
from agent.contracts.transport import (
    TransportRequest,
    TransportResponse,
    TransportValidationError,
    validate_transport_request,
)


class ApplicationBoundary(ApplicationPort):
    """Transport-neutral application ingress with security and telemetry hooks."""

    def __init__(
        self,
        dispatcher: CommandDispatcher,
        authenticator: Authenticator | None = None,
        authorizer: Authorizer | None = None,
        observability: object | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._authenticator = authenticator or AllowAllAuthenticator()
        self._authorizer = authorizer or AllowAllAuthorizer()
        self._observability = observability or NullObservability()

    def _record(self, event: ExecutionEvent) -> None:
        try:
            self._observability.record(event)
        except Exception:
            # Telemetry is deliberately non-fatal to application execution.
            return None

    @staticmethod
    def _event(request: TransportRequest | None, event_type: ExecutionEventType, outcome: str, command_id: str = "") -> ExecutionEvent:
        context = request.context if isinstance(request, TransportRequest) else None
        return ExecutionEvent.now(
            event_id=str(uuid4()),
            event_type=event_type,
            request_id=context.request_id if context else "unknown",
            correlation_id=context.correlation_id if context else "unknown",
            command_id=command_id,
            outcome=outcome,
        )

    def _response(self, request: TransportRequest | None, command: Command | None, success: bool, code: str, message: str = "", data=None) -> TransportResponse:
        return TransportResponse(
            request_id=request.context.request_id if isinstance(request, TransportRequest) else "",
            correlation_id=request.context.correlation_id if isinstance(request, TransportRequest) else "",
            command_id=command.command_id if isinstance(command, Command) else "",
            success=success,
            code=code,
            message=message,
            data=data,
        )

    def handle(self, request: TransportRequest) -> TransportResponse:
        self._record(self._event(request, ExecutionEventType.REQUEST_RECEIVED, "received"))

        try:
            validate_transport_request(request)
        except TransportValidationError as exc:
            self._record(self._event(request, ExecutionEventType.REQUEST_REJECTED, "invalid_request"))
            return self._response(request, request.command if isinstance(request, TransportRequest) else None, False, "invalid_request", str(exc))

        command = request.command
        auth_result: AuthenticationResult
        try:
            auth_result = self._authenticator.authenticate(request)
        except Exception as exc:
            self._record(self._event(request, ExecutionEventType.AUTHENTICATION_COMPLETED, "failed", command.command_id))
            return self._response(request, command, False, "authentication_failed", str(exc))

        self._record(self._event(request, ExecutionEventType.AUTHENTICATION_COMPLETED, "success" if auth_result.success else "failed", command.command_id))
        if not auth_result.success or auth_result.context is None:
            return self._response(request, command, False, auth_result.code or "authentication_failed", auth_result.message)

        try:
            decision = self._authorizer.authorize(auth_result.context, command)
        except Exception as exc:
            self._record(self._event(request, ExecutionEventType.AUTHORIZATION_COMPLETED, "failed", command.command_id))
            return self._response(request, command, False, "authorization_failed", str(exc))

        self._record(self._event(request, ExecutionEventType.AUTHORIZATION_COMPLETED, "allowed" if decision.allowed else "denied", command.command_id))
        if not decision.allowed:
            return self._response(request, command, False, decision.code or "authorization_denied", decision.message)

        self._record(self._event(request, ExecutionEventType.COMMAND_DISPATCHED, "started", command.command_id))
        result = self._dispatcher.dispatch(command)
        response = self._response(request, command, result.success, result.code, result.message, result.data)
        self._record(self._event(request, ExecutionEventType.REQUEST_COMPLETED, result.code, command.command_id))
        return response
