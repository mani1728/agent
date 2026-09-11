# Path: Version 1_0_0/agent/transport/kafka/commit_policy.py

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional


logger = logging.getLogger(__name__)


class CommitPolicy(str, Enum):
    """
    Kafka offset commit policies.

    AUTO:
        Kafka/librdkafka manages offsets automatically.

    MANUAL:
        Application explicitly commits offsets.

    AFTER_RESPONSE:
        Offset should be committed only after command execution
        and response publication have completed successfully.

    DISABLED:
        No offset commit is performed by the application.
    """

    AUTO = "auto"
    MANUAL = "manual"
    AFTER_RESPONSE = "after_response"
    DISABLED = "disabled"


class CommitState(str, Enum):
    """
    Logical lifecycle state of a consumed command.
    """

    RECEIVED = "received"
    EXECUTING = "executing"
    EXECUTED = "executed"
    RESPONSE_SENT = "response_sent"
    ACKED = "acked"
    FAILED = "failed"


class CommitDecision:
    """
    Result of evaluating whether a Kafka offset may be committed.

    This is deliberately transport-independent at the decision level.
    The actual Kafka commit operation remains in the Kafka adapter.
    """

    def __init__(
        self,
        *,
        allowed: bool,
        reason: str,
        command_id: Optional[str] = None,
        state: Optional[CommitState] = None,
    ) -> None:
        self.allowed = bool(allowed)
        self.reason = str(reason)
        self.command_id = command_id
        self.state = state

    def __bool__(self) -> bool:
        return self.allowed

    def __repr__(self) -> str:
        return (
            "CommitDecision("
            f"allowed={self.allowed!r}, "
            f"reason={self.reason!r}, "
            f"command_id={self.command_id!r}, "
            f"state={self.state!r}"
            ")"
        )


class CommandCommitTracker:
    """
    Tracks the logical lifecycle of a consumed command.

    The tracker does NOT:
        - call Kafka
        - commit offsets
        - retry commands
        - execute commands
        - persist state

    It only records enough state for CommitPolicy to make a safe
    decision later.
    """

    def __init__(
        self,
        command_id: str,
    ) -> None:
        if not command_id:
            raise ValueError(
                "command_id must not be empty"
            )

        self.command_id = str(command_id)
        self.state = CommitState.RECEIVED

    def mark_executing(self) -> None:
        self.state = CommitState.EXECUTING

    def mark_executed(self) -> None:
        self.state = CommitState.EXECUTED

    def mark_response_sent(self) -> None:
        self.state = CommitState.RESPONSE_SENT

    def mark_acked(self) -> None:
        self.state = CommitState.ACKED

    def mark_failed(self) -> None:
        self.state = CommitState.FAILED

    def can_commit_after_response(self) -> bool:
        return self.state == CommitState.RESPONSE_SENT


class KafkaCommitPolicy:
    """
    Determines when a Kafka command offset is logically eligible
    for acknowledgement/commit.

    Phase 1 behavior:
        The existing configuration uses Kafka auto-commit.

        Therefore this policy is informational and does not perform
        any Kafka commit operation.

    Later phases can use this class to introduce:
        consumed -> executed -> response sent -> commit

    semantics without embedding commit logic inside the business layer.
    """

    def __init__(
        self,
        policy: CommitPolicy | str = CommitPolicy.AUTO,
    ) -> None:
        self.policy = self._normalize_policy(policy)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_policy(
        policy: CommitPolicy | str,
    ) -> CommitPolicy:
        if isinstance(policy, CommitPolicy):
            return policy

        try:
            return CommitPolicy(
                str(policy).strip().lower()
            )
        except ValueError as exc:
            raise ValueError(
                f"Unsupported Kafka commit policy: {policy!r}"
            ) from exc

    @classmethod
    def from_config(
        cls,
        config: Any,
    ) -> "KafkaCommitPolicy":
        """
        Build a policy from the existing configuration.

        Compatibility rule:
            kafka.enable_auto_commit=true
                -> AUTO

            kafka.enable_auto_commit=false
                -> MANUAL

        An explicit kafka.commit_policy, if present, takes precedence.
        """

        explicit_policy = None

        try:
            explicit_policy = config.get(
                "kafka.commit_policy",
                None,
            )
        except AttributeError:
            pass

        if explicit_policy:
            return cls(
                explicit_policy
            )

        try:
            auto_commit = config.get(
                "kafka.enable_auto_commit",
                True,
            )
        except AttributeError:
            auto_commit = True

        if bool(auto_commit):
            return cls(
                CommitPolicy.AUTO
            )

        return cls(
            CommitPolicy.MANUAL
        )

    # ------------------------------------------------------------------
    # Decision logic
    # ------------------------------------------------------------------

    def evaluate(
        self,
        tracker: CommandCommitTracker,
    ) -> CommitDecision:
        """
        Determine whether the command is currently eligible for commit.
        """

        if not isinstance(
            tracker,
            CommandCommitTracker,
        ):
            raise TypeError(
                "tracker must be CommandCommitTracker"
            )

        if self.policy == CommitPolicy.AUTO:
            return CommitDecision(
                allowed=False,
                reason=(
                    "Application does not control the offset; "
                    "Kafka auto-commit is enabled."
                ),
                command_id=tracker.command_id,
                state=tracker.state,
            )

        if self.policy == CommitPolicy.DISABLED:
            return CommitDecision(
                allowed=False,
                reason=(
                    "Offset commits are explicitly disabled."
                ),
                command_id=tracker.command_id,
                state=tracker.state,
            )

        if self.policy == CommitPolicy.MANUAL:
            if tracker.state in {
                CommitState.RECEIVED,
                CommitState.EXECUTING,
            }:
                return CommitDecision(
                    allowed=False,
                    reason=(
                        "Command has not completed execution."
                    ),
                    command_id=tracker.command_id,
                    state=tracker.state,
                )

            if tracker.state == CommitState.FAILED:
                return CommitDecision(
                    allowed=False,
                    reason=(
                        "Failed command must not be committed "
                        "by the generic manual policy."
                    ),
                    command_id=tracker.command_id,
                    state=tracker.state,
                )

            return CommitDecision(
                allowed=True,
                reason=(
                    "Manual commit is allowed after command "
                    "execution has completed."
                ),
                command_id=tracker.command_id,
                state=tracker.state,
            )

        if self.policy == CommitPolicy.AFTER_RESPONSE:
            if tracker.state == CommitState.RESPONSE_SENT:
                return CommitDecision(
                    allowed=True,
                    reason=(
                        "Response has been successfully published."
                    ),
                    command_id=tracker.command_id,
                    state=tracker.state,
                )

            return CommitDecision(
                allowed=False,
                reason=(
                    "Offset cannot be committed before "
                    "response publication."
                ),
                command_id=tracker.command_id,
                state=tracker.state,
            )

        return CommitDecision(
            allowed=False,
            reason="Unknown commit policy.",
            command_id=tracker.command_id,
            state=tracker.state,
        )

    def should_commit(
        self,
        tracker: CommandCommitTracker,
    ) -> bool:
        """
        Convenience method returning only the commit decision.
        """

        return bool(
            self.evaluate(tracker)
        )

    # ------------------------------------------------------------------
    # Runtime information
    # ------------------------------------------------------------------

    @property
    def is_application_managed(self) -> bool:
        return self.policy in {
            CommitPolicy.MANUAL,
            CommitPolicy.AFTER_RESPONSE,
        }

    @property
    def is_auto_commit(self) -> bool:
        return self.policy == CommitPolicy.AUTO

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def describe(self) -> dict[str, Any]:
        return {
            "policy": self.policy.value,
            "application_managed": self.is_application_managed,
            "auto_commit": self.is_auto_commit,
        }


__all__ = [
    "CommitPolicy",
    "CommitState",
    "CommitDecision",
    "CommandCommitTracker",
    "KafkaCommitPolicy",
]