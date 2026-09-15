"""Concrete HTTP/JSON transport adapter.

This module is the only place where the standard-library HTTP server is used.
The application receives only the transport-neutral ApplicationPort contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from agent.contracts.commands import CommandValidationError, make_command
from agent.contracts.ports import ApplicationPort
from agent.contracts.transport import ExecutionContext, TransportRequest, TransportResponse, TransportValidationError


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


class HTTPTransportError(ValueError):
    """Raised for protocol-level HTTP transport failures."""


class HTTPTransportAdapter:
    """Translate HTTP/JSON requests to and from the ApplicationPort."""

    PATH = "/command"

    def __init__(self, application: ApplicationPort) -> None:
        self._application = application

    @staticmethod
    def _parse_object(body: bytes) -> dict[str, Any]:
        if not body:
            raise HTTPTransportError("Request body is required.")
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPTransportError("Request body must be valid UTF-8 JSON.") from exc
        if not isinstance(value, dict):
            raise HTTPTransportError("Request body must be a JSON object.")
        return value

    @staticmethod
    def _request_from_json(value: dict[str, Any]) -> TransportRequest:
        request_id = value.get("request_id")
        correlation_id = value.get("correlation_id")
        raw_command = value.get("command")
        if not isinstance(request_id, str) or not request_id.strip():
            raise TransportValidationError("request_id must be a non-empty string")
        if not isinstance(correlation_id, str) or not correlation_id.strip():
            raise TransportValidationError("correlation_id must be a non-empty string")
        if not isinstance(raw_command, dict):
            raise TransportValidationError("command must be a JSON object")
        required = ("command_id", "command_type", "schema_version", "timestamp", "payload")
        missing = [field for field in required if field not in raw_command]
        if missing:
            raise TransportValidationError("command is missing required fields")
        command = make_command(
            command_id=raw_command["command_id"],
            command_type=raw_command["command_type"],
            correlation_id=correlation_id,
            schema_version=raw_command["schema_version"],
            timestamp=raw_command["timestamp"],
            payload=raw_command["payload"],
        )
        return TransportRequest(ExecutionContext(request_id, correlation_id, {}), command)

    @staticmethod
    def _response_body(response: TransportResponse) -> bytes:
        value = {
            "request_id": response.request_id,
            "correlation_id": response.correlation_id,
            "command_id": response.command_id,
            "success": response.success,
            "code": response.code,
            "message": response.message,
            "data": response.data,
        }
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise HTTPTransportError("Response serialization failed.") from exc

    @staticmethod
    def _status_for(response: TransportResponse) -> int:
        if response.success:
            return 200
        return {
            "invalid_request": 400,
            "invalid_command": 400,
            "unsupported_schema": 400,
            "authentication_failed": 401,
            "authorization_denied": 403,
            "authorization_failed": 500,
            "unknown_command": 404,
            "execution_failed": 500,
        }.get(response.code, 500)

    def handle_json(self, body: bytes) -> HTTPResponse:
        try:
            value = self._parse_object(body)
            request = self._request_from_json(value)
        except (HTTPTransportError, TransportValidationError, CommandValidationError) as exc:
            error = TransportResponse("", "", "", False, "invalid_request", str(exc))
            return HTTPResponse(400, self._response_body(error))
        try:
            response = self._application.handle(request)
        except Exception:
            error = TransportResponse(request.context.request_id, request.context.correlation_id,
                                      request.command.command_id, False, "application_error",
                                      "Application request failed.")
            return HTTPResponse(500, self._response_body(error))
        try:
            body_bytes = self._response_body(response)
        except HTTPTransportError:
            error = TransportResponse(response.request_id, response.correlation_id, response.command_id,
                                      False, "transport_error", "Response serialization failed.")
            return HTTPResponse(500, self._response_body(error))
        return HTTPResponse(self._status_for(response), body_bytes)

    def create_server(self, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
        adapter = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.path != adapter.PATH:
                    self._write(404, {"code": "not_found", "message": "Endpoint not found."})
                    return
                length_header = self.headers.get("Content-Length")
                try:
                    length = int(length_header) if length_header is not None else -1
                except ValueError:
                    length = -1
                if length < 0 or length > 1024 * 1024:
                    self._write(400, {"code": "invalid_request", "message": "Invalid request body length."})
                    return
                result = adapter.handle_json(self.rfile.read(length))
                self.send_response(result.status)
                self.send_header("Content-Type", result.content_type)
                self.send_header("Content-Length", str(len(result.body)))
                self.end_headers()
                self.wfile.write(result.body)

            def _write(self, status: int, value: dict[str, Any]) -> None:
                body = json.dumps(value, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                return None

        return ThreadingHTTPServer((host, port), Handler)
