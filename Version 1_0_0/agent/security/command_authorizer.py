# Path: Version 1_0_0/agent/security/command_authorizer.py

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

from agent.contracts.command import CommandEnvelope


logger = logging.getLogger(__name__)


class AuthorizationError(RuntimeError):
    """Base error for command authorization failures."""


class CommandAuthorizationError(AuthorizationError):
    """Raised when a command is not authorized."""


@dataclass(frozen=True)
class AuthorizationRule:
    """
    Authorization rule for a target class and its allowed methods.

    An empty methods collection means that no methods are allowed.
    """

    target_class: str
    methods: frozenset[str] = field(default_factory=frozenset)
    max_priority: Optional[int] = None
    required_metadata: Mapping[str, Any] = field(
        default_factory=dict
    )

    def allows(
        self,
        command: CommandEnvelope,
    ) -> bool:
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


class CommandAuthorizer:
    """
    Transport-independent command authorization.

    Authorization is deny-by-default. A command must match an explicit
    allowlist rule before it can be executed.

    This class deliberately does not perform:
      - authentication
      - token validation
      - HMAC validation
      - Kafka/HTTP processing
      - MT5 execution

    Authentication establishes who sent a command; this class decides
    whether that command is permitted.
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

        self._rules = self._validate_rules(
            configured_rules
        )

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

            if not rule.methods:
                continue

            if any(
                not isinstance(method, str)
                or not method.strip()
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

    @property
    def rules(self) -> tuple[AuthorizationRule, ...]:
        return self._rules

    @property
    def default_allow(self) -> bool:
        return self._default_allow

    def is_authorized(
        self,
        command: CommandEnvelope,
    ) -> bool:
        if not isinstance(command, CommandEnvelope):
            raise TypeError(
                "command must be a CommandEnvelope"
            )

        for rule in self._rules:
            if rule.allows(command):
                return True

        return self._default_allow

    def authorize(
        self,
        command: CommandEnvelope,
    ) -> None:
        """
        Authorize a command or raise CommandAuthorizationError.

        No sensitive command parameters are included in the error message.
        """
        if self.is_authorized(command):
            return

        raise CommandAuthorizationError(
            "Command is not authorized: "
            f"{command.target_class}.{command.target_method}"
        )

    def authorize_or_false(
        self,
        command: CommandEnvelope,
    ) -> bool:
        """
        Compatibility/helper form that returns False instead of raising.
        """
        try:
            return self.is_authorized(command)
        except (TypeError, ValueError):
            return False

    def find_rule(
        self,
        command: CommandEnvelope,
    ) -> Optional[AuthorizationRule]:
        """
        Return the first matching authorization rule.

        A matching target/method is returned even if a later constraint
        such as max_priority or required metadata rejects the command.
        """
        if not isinstance(command, CommandEnvelope):
            raise TypeError(
                "command must be a CommandEnvelope"
            )

        for rule in self._rules:
            if (
                command.target_class == rule.target_class
                and command.target_method in rule.methods
            ):
                return rule

        return None

    def allowed_methods(
        self,
        target_class: str,
    ) -> frozenset[str]:
        """
        Return the union of explicitly allowed methods for a target.
        """
        methods: set[str] = set()

        for rule in self._rules:
            if rule.target_class == target_class:
                methods.update(rule.methods)

        return frozenset(methods)

    def add_rule(
        self,
        rule: AuthorizationRule,
    ) -> None:
        """
        Add an authorization rule at runtime.

        Runtime mutation is explicit and local; persistence/config reload
        is intentionally handled elsewhere.
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
        """
        Remove matching rules and return the number of removed rules.
        """
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


def build_default_authorizer() -> CommandAuthorizer:
    """
    Build the production-safe default authorizer.

    The default policy is deny-by-default with the explicitly supported
    Mt5_Manager command methods.
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