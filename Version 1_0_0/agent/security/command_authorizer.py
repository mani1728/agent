# Path: Version 1_0_0/agent/security/command_authorizer.py

"""Transport-independent command authorization.

Responsibilities
----------------
- Decide whether a given ``CommandEnvelope`` is permitted to execute.
- Provide a central, explicit authorization surface with two entry
  points:
    - ``allows(command) -> bool``  — non-raising check.
    - ``require(command) -> None`` — raising check.

This module intentionally does NOT perform:
- authentication (who sent the command),
- token / HMAC validation,
- Kafka / HTTP / MT5 processing.

Authentication establishes identity; authorization decides whether
the identified caller may run the requested method.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

from agent.contracts.command import CommandEnvelope


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------

class AuthorizationError(RuntimeError):
    """Base error for command authorization failures."""


class CommandAuthorizationError(AuthorizationError):
    """Raised when a command is not authorized.

    The message contains only ``target_class`` and ``target_method``
    (never payload params or secrets), so it is safe to log verbatim.
    """


# ----------------------------------------------------------------------
# Rule model
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class AuthorizationRule:
    """Authorization rule for a target class and its allowed methods.

    An empty ``methods`` collection means the rule allows nothing and
    is discarded at validation time.
    """

    target_class: str
    methods: frozenset[str] = field(default_factory=frozenset)
    max_priority: Optional[int] = None
    required_metadata: Mapping[str, Any] = field(default_factory=dict)

    def allows(self, command: CommandEnvelope) -> bool:
        """Return True if this rule permits ``command``."""
        if command.target_class != self.target_class:
            return False

        if command.target_method not in self.methods:
            return False

        if (
            self.max_priority is not None
            and command.priority > self.max_priority
        ):
            return False

        for key, expected in self.required_metadata.items():
            if command.metadata.get(key) != expected:
                return False

        return True


# ----------------------------------------------------------------------
# Authorizer
# ----------------------------------------------------------------------

class CommandAuthorizer:
    """Central, transport-independent command authorizer.

    Authorization is **deny-by-default**: a command must match an
    explicit allowlist rule before it can be executed.

    Two canonical entry points:

    ``allows(command) -> bool``
        Non-raising check. Useful for conditional routing, tests, or
        UI feedback. Never raises on a normal, well-formed command.

    ``require(command) -> None``
        Raising check. Raises ``CommandAuthorizationError`` when the
        command is not permitted. This is the ONLY method that
        runtime execution paths should call before dispatch.
    """

    DEFAULT_RULES: tuple[AuthorizationRule, ...] = (
        AuthorizationRule(
            target_class="Mt5_Manager",
            methods=frozenset(
                {
                    "manage_connection",
                    "manage_symbols",
                    "manage_market_book",
                    "fetch_data",
                    "trade_manager",
                    "manage_positions_history",
                }
            ),
        ),
    )

    def __init__(
        self,
        rules: Optional[Iterable[AuthorizationRule]] = None,
        *,
        default_allow: bool = False,
    ) -> None:
        self._default_allow = bool(default_allow)

        configured_rules = (
            tuple(rules)
            if rules is not None
            else self.DEFAULT_RULES
        )

        self._rules = self._validate_rules(configured_rules)

    # ------------------------------------------------------------------
    # Rule validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_rules(
        rules: Iterable[AuthorizationRule],
    ) -> tuple[AuthorizationRule, ...]:
        result: list[AuthorizationRule] = []

        for rule in rules:
            if not isinstance(rule, AuthorizationRule):
                raise TypeError(
                    "Authorization rules must be "
                    "AuthorizationRule instances"
                )

            if not rule.target_class.strip():
                raise ValueError(
                    "Authorization rule target_class cannot be empty"
                )

            # Rules with no allowed methods are silently dropped: they
            # cannot authorize anything.
            if not rule.methods:
                continue

            if any(
                not isinstance(method, str) or not method.strip()
                for method in rule.methods
            ):
                raise ValueError(
                    "Authorization rule methods must contain "
                    "non-empty strings"
                )

            if (
                rule.max_priority is not None
                and rule.max_priority < 0
            ):
                raise ValueError(
                    "max_priority cannot be negative"
                )

            result.append(rule)

        return tuple(result)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def rules(self) -> tuple[AuthorizationRule, ...]:
        return self._rules

    @property
    def default_allow(self) -> bool:
        return self._default_allow

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def allows(self, command: CommandEnvelope) -> bool:
        """Return True if ``command`` is authorized.

        Never raises on a valid ``CommandEnvelope``. Raises ``TypeError``
        if ``command`` is not a ``CommandEnvelope``.

        This is the **non-raising** entry point. It is the preferred
        name per the Patch 5 contract.
        """
        if not isinstance(command, CommandEnvelope):
            raise TypeError("command must be a CommandEnvelope")

        for rule in self._rules:
            if rule.allows(command):
                return True

        return self._default_allow

    def require(self, command: CommandEnvelope) -> None:
        """Authorize ``command`` or raise ``CommandAuthorizationError``.

        This is the **raising** entry point. Runtime execution paths
        MUST call ``require`` before dispatch, so that unauthorized
        commands fail loudly and early.

        The error message contains only the target class and method,
        never payload parameters or secrets.
        """
        if self.allows(command):
            return

        raise CommandAuthorizationError(
            "Command is not authorized: "
            f"{command.target_class}.{command.target_method}"
        )

    # ------------------------------------------------------------------
    # Backwards-compatible aliases
    # ------------------------------------------------------------------

    def is_authorized(self, command: CommandEnvelope) -> bool:
        """Alias for :meth:`allows` (kept for backward compatibility)."""
        return self.allows(command)

    def authorize(self, command: CommandEnvelope) -> None:
        """Alias for :meth:`require` (kept for backward compatibility)."""
        return self.require(command)

    def authorize_or_false(self, command: CommandEnvelope) -> bool:
        """Return False instead of raising on malformed input.

        Kept for backward compatibility with callers that preferred a
        boolean outcome over exceptions.
        """
        try:
            return self.allows(command)
        except (TypeError, ValueError):
            return False

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def find_rule(
        self,
        command: CommandEnvelope,
    ) -> Optional[AuthorizationRule]:
        """Return the first rule matching class+method (ignoring extra
        constraints like ``max_priority`` or ``required_metadata``).
        """
        if not isinstance(command, CommandEnvelope):
            raise TypeError("command must be a CommandEnvelope")

        for rule in self._rules:
            if (
                command.target_class == rule.target_class
                and command.target_method in rule.methods
            ):
                return rule

        return None

    def allowed_methods(self, target_class: str) -> frozenset[str]:
        """Return the union of explicitly allowed methods for a target."""
        methods: set[str] = set()

        for rule in self._rules:
            if rule.target_class == target_class:
                methods.update(rule.methods)

        return frozenset(methods)

    # ------------------------------------------------------------------
    # Runtime rule mutation (tests, config reload)
    # ------------------------------------------------------------------

    def add_rule(self, rule: AuthorizationRule) -> None:
        """Add a rule at runtime.

        Runtime mutation is explicit and local. Persistence and config
        reload are handled elsewhere.
        """
        validated = self._validate_rules((rule,))
        if not validated:
            return

        self._rules = self._rules + validated

    def remove_rules(
        self,
        *,
        target_class: Optional[str] = None,
        target_method: Optional[str] = None,
    ) -> int:
        """Remove matching rules; return the number of removed rules."""
        if target_class is None and target_method is None:
            raise ValueError(
                "At least one rule selector is required"
            )

        original_count = len(self._rules)
        retained: list[AuthorizationRule] = []

        for rule in self._rules:
            target_matches = (
                target_class is None
                or rule.target_class == target_class
            )
            method_matches = (
                target_method is None
                or target_method in rule.methods
            )

            if target_matches and method_matches:
                continue

            retained.append(rule)

        self._rules = tuple(retained)

        return original_count - len(self._rules)


# ----------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------

def build_default_authorizer() -> CommandAuthorizer:
    """Build the production-safe default authorizer.

    Default policy: deny-by-default, with an explicit allowlist for
    the supported ``Mt5_Manager`` methods.
    """
    return CommandAuthorizer(
        rules=CommandAuthorizer.DEFAULT_RULES,
        default_allow=False,
    )


__all__ = [
    "AuthorizationError",
    "AuthorizationRule",
    "CommandAuthorizationError",
    "CommandAuthorizer",
    "build_default_authorizer",
]