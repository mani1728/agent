# Path: core/"""
# Result/response builder.
#
# This module converts command execution results into the canonical
# ResponseEnvelope contract.
#
# Responsibilities:
# - Build successful responses.
# - Build error responses.
# - Preserve correlation IDs.
# - Preserve request metadata such as request_index.
# - Keep response construction independent from Kafka/HTTP/MT5.
#
# Non-responsibilities:
# - Transport delivery.
# - Kafka serialization.
# - HTTP communication.
# - Retry/reliability.
# - Command execution.
# """
#
# from __future__ import annotations
#
# from typing import Any, Mapping
#
# from agent.contracts.command import CommandEnvelope
# from agent.contracts.response import ResponseEnvelope
#
#
# DEFAULT_RESPONSE_SCHEMA = "Mt5ResultV1"
#
#
# class ResultBuilder:
#     """
#     Build canonical ResponseEnvelope objects.
#
#     The builder exists as a small compatibility boundary between
#     execution code and the response contract.
#
#     It deliberately contains no transport-specific logic.
#     """
#
#     def __init__(
#         self,
#         schema_version: str = DEFAULT_RESPONSE_SCHEMA,
#     ) -> None:
#         if not isinstance(schema_version, str):
#             raise TypeError("schema_version must be a string.")
#
#         schema_version = schema_version.strip()
#
#         if not schema_version:
#             raise ValueError(
#                 "schema_version must be a non-empty string."
#             )
#
#         self._schema_version = schema_version
#
#     @property
#     def schema_version(self) -> str:
#         """Return the configured response schema version."""
#
#         return self._schema_version
#
#     def success(
#         self,
#         *,
#         correlation_id: str,
#         result: Any = None,
#         metadata: Mapping[str, Any] | None = None,
#     ) -> ResponseEnvelope:
#         """
#         Build a successful response.
#
#         ``result`` maps to the canonical ``data`` field.
#         """
#
#         return ResponseEnvelope.success(
#             correlation_id=correlation_id,
#             data=result,
#             schema_version=self._schema_version,
#             metadata=dict(metadata or {}),
#         )
#
#     def error(
#         self,
#         *,
#         correlation_id: str,
#         error_code: str,
#         error_message: str,
#         metadata: Mapping[str, Any] | None = None,
#     ) -> ResponseEnvelope:
#         """Build an error response."""
#
#         return ResponseEnvelope.error(
#             correlation_id=correlation_id,
#             error_code=error_code,
#             error_message=error_message,
#             schema_version=self._schema_version,
#             metadata=dict(metadata or {}),
#         )
#
#     def from_execution(
#         self,
#         command: CommandEnvelope,
#         result: Any,
#         *,
#         metadata: Mapping[str, Any] | None = None,
#     ) -> ResponseEnvelope:
#         """
#         Build a successful response directly from a CommandEnvelope.
#
#         Command metadata is preserved where appropriate.
#         Explicit metadata takes precedence.
#         """
#
#         if not isinstance(command, CommandEnvelope):
#             raise TypeError(
#                 "command must be a CommandEnvelope."
#             )
#
#         response_metadata = self._command_metadata(command)
#
#         if metadata:
#             response_metadata.update(dict(metadata))
#
#         return self.success(
#             correlation_id=command.correlation_id,
#             result=result,
#             metadata=response_metadata,
#         )
#
#     def from_exception(
#         self,
#         command: CommandEnvelope,
#         exc: Exception,
#         *,
#         error_code: str = "EXECUTION_ERROR",
#         metadata: Mapping[str, Any] | None = None,
#     ) -> ResponseEnvelope:
#         """
#         Build an error response from an exception.
#
#         Exception details are bounded before being returned as a protocol
#         error message.
#         """
#
#         if not isinstance(command, CommandEnvelope):
#             raise TypeError(
#                 "command must be a CommandEnvelope."
#             )
#
#         if not isinstance(exc, Exception):
#             raise TypeError(
#                 "exc must be an Exception."
#             )
#
#         response_metadata = self._command_metadata(command)
#
#         if metadata:
#             response_metadata.update(dict(metadata))
#
#         message = str(exc).strip()
#
#         if not message:
#             message = "Command execution failed."
#
#         # Prevent accidental transport-level payload inflation.
#         message = message[:1000]
#
#         return self.error(
#             correlation_id=command.correlation_id,
#             error_code=error_code,
#             error_message=message,
#             metadata=response_metadata,
#         )
#
#     @staticmethod
#     def _command_metadata(
#         command: CommandEnvelope,
#     ) -> dict[str, Any]:
#         """
#         Extract safe response metadata from a command.
#
#         The command contract is already responsible for sanitizing
#         sensitive metadata. We therefore preserve the canonical metadata
#         rather than reconstructing or duplicating it.
#         """
#
#         metadata = dict(command.metadata or {})
#
#         # These fields are useful for legacy compatibility and diagnostics.
#         if command.command_id:
#             metadata.setdefault(
#                 "command_id",
#                 command.command_id,
#             )
#
#         if command.target_class:
#             metadata.setdefault(
#                 "target_class",
#                 command.target_class,
#             )
#
#         if command.target_method:
#             metadata.setdefault(
#                 "target_method",
#                 command.target_method,
#             )
#
#         return metadata
#
#
# # ----------------------------------------------------------------------
# # Functional compatibility helpers
# # ----------------------------------------------------------------------
#
# _default_builder = ResultBuilder()
#
#
# def build_success_response(
#     correlation_id: str,
#     result: Any = None,
#     *,
#     metadata: Mapping[str, Any] | None = None,
#     schema_version: str = DEFAULT_RESPONSE_SCHEMA,
# ) -> ResponseEnvelope:
#     """
#     Functional helper for callers that do not need a ResultBuilder
#     instance.
#     """
#
#     if schema_version == DEFAULT_RESPONSE_SCHEMA:
#         builder = _default_builder
#     else:
#         builder = ResultBuilder(schema_version)
#
#     return builder.success(
#         correlation_id=correlation_id,
#         result=result,
#         metadata=metadata,
#     )
#
#
# def build_error_response(
#     correlation_id: str,
#     error_code: str,
#     error_message: str,
#     *,
#     metadata: Mapping[str, Any] | None = None,
#     schema_version: str = DEFAULT_RESPONSE_SCHEMA,
# ) -> ResponseEnvelope:
#     """Functional helper for building an error response."""
#
#     if schema_version == DEFAULT_RESPONSE_SCHEMA:
#         builder = _default_builder
#     else:
#         builder = ResultBuilder(schema_version)
#
#     return builder.error(
#         correlation_id=correlation_id,
#         error_code=error_code,
#         error_message=error_message,
#         metadata=metadata,
#     )
#
#
# __all__ = [
#     "DEFAULT_RESPONSE_SCHEMA",
#     "ResultBuilder",
#     "build_success_response",
#     "build_error_response",
# ]

