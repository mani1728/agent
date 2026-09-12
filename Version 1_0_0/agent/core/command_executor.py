# Path: Version 1_0_0/agent/core/command_executor.py

# -*- coding: utf-8 -*-
"""
command_executor.py
-------------------
Core command execution boundary.

مسئولیت:
- دریافت CommandEnvelope
- واگذاری اجرای command به Dispatcher
- برگرداندن ResponseEnvelope
- نگه‌داشتن execution logic خارج از Transport

در این مرحله:
- Kafka ندارد
- HTTP ندارد
- Retry ندارد
- Persistence ندارد
- PriorityExecutor ندارد
- Lifecycle / Worker ندارد

اصل migration:
    Preserve behavior first, improve architecture second.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope
from agent.security.command_authorizer import (
    CommandAuthorizationError,
    CommandAuthorizer,
    build_default_authorizer,
)

from .dispatcher import Dispatcher
from agent.core.exceptions import (
    ValidationError,
    RetryableExternalError,
    PermanentExternalError,
)

logger = logging.getLogger(__name__)


class CommandExecutor:
    """
    Thin execution boundary between Agent Core and Dispatcher.

    معماری فعلی:

        CommandEnvelope
              |
              v
        CommandExecutor
              |
              v
          Dispatcher
              |
              v
          Mt5_Manager
              |
              v
        ResponseEnvelope
    """

    def __init__(
        self,
        dispatcher: Optional[Dispatcher] = None,
        *,
        authorizer: Optional[CommandAuthorizer] = None,
    ) -> None:
        self._dispatcher = dispatcher or Dispatcher()
        self._authorizer = authorizer or build_default_authorizer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        command: CommandEnvelope,
    ) -> ResponseEnvelope:
        """
        Execute one canonical CommandEnvelope.

        تمام routing واقعی در Dispatcher انجام می‌شود.
        """

        if not isinstance(command, CommandEnvelope):
            raise TypeError(
                "command must be an instance of CommandEnvelope"
            )

        try:
            self._authorizer.authorize(command)
        except CommandAuthorizationError as exc:
            return ResponseEnvelope.error(
                correlation_id=command.correlation_id,
                error_code="COMMAND_UNAUTHORIZED",
                error_message=str(exc),
                metadata={
                    "target_class": command.target_class,
                    "target_method": command.target_method,
                },
            )

        return self._dispatcher.dispatch(command)

    def execute_dict(
        self,
        payload: Mapping[str, Any],
        *,
        correlation_id: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> ResponseEnvelope:
        """
        Compatibility boundary for legacy callers.

        Raw dictionaries are converted to CommandEnvelope before
        entering the execution layer.
        """

        if not isinstance(payload, Mapping):
            raise TypeError(
                "payload must be a mapping"
            )

        command = CommandEnvelope.from_dict(
            dict(payload),
            correlation_id=correlation_id,
            priority=priority,
        )

        return self.execute(command)


__all__ = [
    "CommandExecutor",
]
