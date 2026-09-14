from agent.application.dispatcher import CommandDispatcher
from agent.contracts.models import Command
from agent.contracts.ports import ApplicationPort
from agent.contracts.transport import TransportRequest, TransportResponse, TransportValidationError, validate_transport_request


class ApplicationBoundary(ApplicationPort):
    """Transport-neutral application entry point over the command dispatcher."""

    def __init__(self, dispatcher: CommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def handle(self, request: TransportRequest) -> TransportResponse:
        try:
            validate_transport_request(request)
        except TransportValidationError as exc:
            command = request.command if isinstance(request, TransportRequest) else None
            return TransportResponse(
                request_id=request.context.request_id if isinstance(request, TransportRequest) else "",
                correlation_id=(request.context.correlation_id if isinstance(request, TransportRequest) else ""),
                command_id=command.command_id if isinstance(command, Command) else "",
                success=False,
                code="invalid_request",
                message=str(exc),
            )

        result = self._dispatcher.dispatch(request.command)
        return TransportResponse(
            request_id=request.context.request_id,
            correlation_id=request.context.correlation_id,
            command_id=result.command_id,
            success=result.success,
            code=result.code,
            message=result.message,
            data=result.data,
        )
