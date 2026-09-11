# Path: Version 1_0_0/agent/core/"""
# Command execution layer.
#
# Phase 1 responsibility:
# - Receive a canonical CommandEnvelope.
# - Delegate command routing/execution to CommandDispatcher.
# - Convert execution results into ResponseEnvelope.
# - Preserve correlation/request context.
# - Keep transport-independent.
#
# This module intentionally does NOT:
# - consume Kafka messages
# - send Kafka/HTTP responses
# - import MetaTrader5
# - implement retry/reliability
# - manage worker threads
# - perform transport acknowledgement
# - persist commands
# """
#
# from __future__ import annotations
#
# from time import perf_counter
# from typing import Any
#
# from agent.contracts.command import CommandEnvelope
# from agent.contracts.response import ResponseEnvelope, ResponseStatus
# from agent.core.dispatcher import (
#     CommandDispatcher,
#     DispatcherError,
# )
#
#
# class CommandExecutionError(Exception):
#     """Base exception for command execution failures."""
#
#
# class CommandExecutor:
#     """
#     Executes canonical commands through a CommandDispatcher.
#
#     The executor is intentionally transport-agnostic.
#
#     Flow:
#
#         CommandEnvelope
#               |
#               v
#         CommandExecutor
#               |
#               v
#         CommandDispatcher
#               |
#               v
#         registered target
#               |
#               v
#            result
#               |
#               v
#         ResponseEnvelope
#     """
#
#     def __init__(
#         self,
#         dispatcher: CommandDispatcher,
#         *,
#         schema_version: str = "Mt5ResultV1",
#     ) -> None:
#         if not isinstance(dispatcher, CommandDispatcher):
#             raise TypeError(
#                 "dispatcher must be an instance of CommandDispatcher."
#             )
#
#         if not isinstance(schema_version, str) or not schema_version.strip():
#             raise ValueError(
#                 "schema_version must be a non-empty string."
#             )
#
#         self._dispatcher = dispatcher
#         self._schema_version = schema_version.strip()
#
#     @property
#     def dispatcher(self) -> CommandDispatcher:
#         """Return the configured dispatcher."""
#
#         return self._dispatcher
#
#     @property
#     def schema_version(self) -> str:
#         """Return the response schema version."""
#
#         return self._schema_version
#
#     def execute(
#         self,
#         command: CommandEnvelope,
#         *,
#         metadata: dict[str, Any] | None = None,
#     ) -> ResponseEnvelope:
#         """
#         Execute a command and return a canonical ResponseEnvelope.
#
#         Execution exceptions are converted into an error response so that
#         the caller does not need to know how the target was dispatched.
#
#         The original exception is not exposed through the response payload.
#         """
#
#         if not isinstance(command, CommandEnvelope):
#             raise TypeError(
#                 "execute() expects a CommandEnvelope instance."
#             )
#
#         started = perf_counter()
#
#         response_metadata: dict[str, Any] = {}
#
#         if isinstance(command.metadata, dict):
#             response_metadata.update(command.metadata)
#
#         if metadata:
#             response_metadata.update(metadata)
#
#         # Keep the request index available to callers that still depend on
#         # the legacy command/result correlation semantics.
#         if command.metadata.get("request_index") is not None:
#             response_metadata.setdefault(
#                 "request_index",
#                 command.metadata["request_index"],
#             )
#
#         try:
#             result = self._dispatcher.dispatch(command)
#
#             elapsed_ms = self._elapsed_ms(started)
#
#             response_metadata["elapsed_ms"] = elapsed_ms
#
#             return ResponseEnvelope.success(
#                 correlation_id=command.correlation_id,
#                 data=result,
#                 schema_version=self._schema_version,
#                 metadata=response_metadata,
#             )
#
#         except Exception as exc:
#             elapsed_ms = self._elapsed_ms(started)
#
#             response_metadata["elapsed_ms"] = elapsed_ms
#
#             error_code = self._error_code(exc)
#
#             return ResponseEnvelope.error(
#                 correlation_id=command.correlation_id,
#                 error_code=error_code,
#                 error_message=self._safe_error_message(exc),
#                 schema_version=self._schema_version,
#                 metadata=response_metadata,
#             )
#
#     def execute_or_raise(
#         self,
#         command: CommandEnvelope,
#     ) -> Any:
#         """
#         Execute a command and return the raw target result.
#
#         Unlike execute(), this method does not convert exceptions into a
#         ResponseEnvelope.
#
#         It is useful for internal callers that need normal Python exception
#         semantics.
#         """
#
#         if not isinstance(command, CommandEnvelope):
#             raise TypeError(
#                 "execute_or_raise() expects a CommandEnvelope instance."
#             )
#
#         return self._dispatcher.dispatch(command)
#
#     # ------------------------------------------------------------------
#     # Helpers
#     # ------------------------------------------------------------------
#
#     @staticmethod
#     def _elapsed_ms(started: float) -> float:
#         """Calculate elapsed execution time in milliseconds."""
#
#         return round((perf_counter() - started) * 1000.0, 3)
#
#     @staticmethod
#     def _error_code(exc: Exception) -> str:
#         """
#         Map known execution failures to stable error codes.
#
#         Do not expose Python exception class names as protocol-level
#         error codes.
#         """
#
#         if isinstance(exc, DispatcherError):
#             return "DISPATCH_ERROR"
#
#         if isinstance(exc, TypeError):
#             return "INVALID_PARAMETERS"
#
#         if isinstance(exc, ValueError):
#             return "INVALID_COMMAND"
#
#         return "EXECUTION_ERROR"
#
#     @staticmethod
#     def _safe_error_message(exc: Exception) -> str:
#         """
#         Produce a bounded error message.
#
#         Sensitive data should not normally be present in target exceptions.
#         A hard length limit also prevents accidentally returning very large
#         exception messages through the transport layer.
#         """
#
#         message = str(exc).strip()
#
#         if not message:
#             return "Command execution failed."
#
#         return message[:1000]
#
#
# __all__ = [
#     "CommandExecutor",
#     "CommandExecutionError",
# ]

