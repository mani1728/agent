# Path: Version 1_0_0/agent/core/dispatcher.py
"""
Command dispatcher.

Phase 1 responsibility:
- Resolve a command target from an explicit allowlist/registry.
- Dispatch a CommandEnvelope to a registered target.
- Keep transport-independent.
- Avoid dynamic arbitrary getattr-based dispatch.
- Avoid importing Kafka, HTTP, MetaTrader5, or concrete transports.

This module intentionally does NOT:
- consume Kafka messages
- send responses
- execute MT5 operations directly
- perform authorization
- implement retries
- manage persistence
- manage worker lifecycle

Those responsibilities belong to later layers/phases.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from agent.contracts.command import CommandEnvelope


class DispatcherError(Exception):
    """Base exception for dispatcher-related failures."""


class TargetNotRegisteredError(DispatcherError):
    """Raised when a command target class is not registered."""


class MethodNotAllowedError(DispatcherError):
    """Raised when a target method is not explicitly allowed."""


class InvalidTargetError(DispatcherError):
    """Raised when a registered target is invalid."""


@dataclass(frozen=True)
class DispatchTarget:
    """
    Registered dispatch target.

    A target consists of:
    - a target object
    - an explicit set of allowed methods

    The dispatcher never executes arbitrary attributes on the object.
    """

    name: str
    target: Any
    allowed_methods: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Dispatch target name must be a non-empty string.")

        if self.target is None:
            raise ValueError("Dispatch target object cannot be None.")

        if not self.allowed_methods:
            raise ValueError(
                f"Dispatch target '{self.name}' must expose at least one "
                "allowed method."
            )


class CommandDispatcher:
    """
    Transport-independent command dispatcher.

    The dispatcher maps:

        CommandEnvelope.target_class
                    +
        CommandEnvelope.target_method
                    ↓
        registered target object / method

    Example:

        dispatcher.register(
            "Mt5_Manager",
            mt5_manager,
            allowed_methods={
                "manage_connection",
                "manage_symbols",
                "fetch_data",
                "trade_manager",
            },
        )

        result = dispatcher.dispatch(command)

    The registry is intentionally explicit. This prevents the legacy
    arbitrary hasattr/getattr dispatch behavior from becoming an
    accidental remote method execution mechanism.
    """

    def __init__(
        self,
        targets: Mapping[str, DispatchTarget] | None = None,
    ) -> None:
        self._targets: dict[str, DispatchTarget] = {}

        if targets:
            for name, target in targets.items():
                self.register_target(
                    name=name,
                    target=target.target,
                    allowed_methods=target.allowed_methods,
                )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_target(
        self,
        name: str,
        target: Any,
        allowed_methods: set[str] | frozenset[str] | list[str] | tuple[str, ...],
    ) -> None:
        """
        Register or replace a dispatch target.

        Only methods explicitly included in ``allowed_methods`` can be
        dispatched through this dispatcher.
        """

        normalized_name = self._normalize_name(name)
        normalized_methods = self._normalize_methods(allowed_methods)

        if not normalized_methods:
            raise ValueError(
                f"Target '{normalized_name}' must have at least one allowed method."
            )

        for method_name in normalized_methods:
            method = getattr(target, method_name, None)

            if method is None or not callable(method):
                raise InvalidTargetError(
                    f"Target '{normalized_name}' does not provide "
                    f"callable method '{method_name}'."
                )

        self._targets[normalized_name] = DispatchTarget(
            name=normalized_name,
            target=target,
            allowed_methods=frozenset(normalized_methods),
        )

    def unregister_target(self, name: str) -> None:
        """Remove a target from the registry."""

        normalized_name = self._normalize_name(name)
        self._targets.pop(normalized_name, None)

    def has_target(self, name: str) -> bool:
        """Return whether a target is registered."""

        normalized_name = self._normalize_name(name)
        return normalized_name in self._targets

    def registered_targets(self) -> tuple[str, ...]:
        """Return registered target names."""

        return tuple(self._targets.keys())

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, command: CommandEnvelope) -> Any:
        """
        Dispatch a CommandEnvelope to its registered target method.

        Parameters
        ----------
        command:
            Canonical transport-independent CommandEnvelope.

        Returns
        -------
        Any
            Return value of the target method.

        Raises
        ------
        TargetNotRegisteredError
            If target_class is not registered.

        MethodNotAllowedError
            If target_method is not explicitly allowed.

        DispatcherError
            If the command is invalid for dispatch.
        """

        if not isinstance(command, CommandEnvelope):
            raise TypeError(
                "dispatch() expects a CommandEnvelope instance."
            )

        target_name = self._normalize_name(command.target_class)
        method_name = self._normalize_name(command.target_method)

        target_entry = self._targets.get(target_name)

        if target_entry is None:
            raise TargetNotRegisteredError(
                f"Target class '{target_name}' is not registered."
            )

        if method_name not in target_entry.allowed_methods:
            raise MethodNotAllowedError(
                f"Method '{method_name}' is not allowed for "
                f"target '{target_name}'."
            )

        method = getattr(target_entry.target, method_name, None)

        if method is None or not callable(method):
            # This should normally be impossible because registration
            # validates the methods, but the check protects against a
            # mutated target object.
            raise InvalidTargetError(
                f"Registered target '{target_name}' does not provide "
                f"callable method '{method_name}'."
            )

        params = command.params

        if params is None:
            params = {}

        if not isinstance(params, Mapping):
            raise DispatcherError(
                f"Command parameters for '{target_name}.{method_name}' "
                "must be a mapping."
            )

        try:
            return method(**dict(params))
        except TypeError:
            # Do not transform the original execution error into a
            # generic dispatcher error. The caller needs the original
            # TypeError information for response/error handling.
            raise

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def allowed_methods(self, name: str) -> frozenset[str]:
        """Return the explicitly allowed methods for a target."""

        normalized_name = self._normalize_name(name)

        target_entry = self._targets.get(normalized_name)

        if target_entry is None:
            raise TargetNotRegisteredError(
                f"Target class '{normalized_name}' is not registered."
            )

        return target_entry.allowed_methods

    def can_dispatch(
        self,
        target_class: str,
        target_method: str,
    ) -> bool:
        """
        Check whether a target/method pair is explicitly dispatchable.

        This method does not execute anything.
        """

        try:
            target_name = self._normalize_name(target_class)
            method_name = self._normalize_name(target_method)
        except ValueError:
            return False

        target_entry = self._targets.get(target_name)

        if target_entry is None:
            return False

        return method_name in target_entry.allowed_methods

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_name(value: str) -> str:
        """Normalize and validate target/method names."""

        if not isinstance(value, str):
            raise ValueError("Target and method names must be strings.")

        normalized = value.strip()

        if not normalized:
            raise ValueError("Target and method names cannot be empty.")

        return normalized

    @classmethod
    def _normalize_methods(
        cls,
        methods: set[str] | frozenset[str] | list[str] | tuple[str, ...],
    ) -> set[str]:
        """Normalize an iterable of method names."""

        if not isinstance(methods, (set, frozenset, list, tuple)):
            raise TypeError(
                "allowed_methods must be a set, frozenset, list, or tuple."
            )

        normalized: set[str] = set()

        for method in methods:
            normalized.add(cls._normalize_name(method))

        return normalized


# ----------------------------------------------------------------------
# Backward-compatible alias
# ----------------------------------------------------------------------

Dispatcher = CommandDispatcher


__all__ = [
    "CommandDispatcher",
    "Dispatcher",
    "DispatchTarget",
    "DispatcherError",
    "TargetNotRegisteredError",
    "MethodNotAllowedError",
    "InvalidTargetError",
]