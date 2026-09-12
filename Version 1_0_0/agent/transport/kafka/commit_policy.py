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
        Application explicitly commits offsets after execution stage.

    AFTER_RESPONSE:
        Offset is committed only after command execution and response
        publication have completed successfully.

    AFTER_SPOOL:
        Offset is committed only after command/result is safely persisted
        into spool (durability-first mode).

    DISABLED:
        No offset commit is performed by the application.
    """

    AUTO = "auto"
    MANUAL = "manual"
    AFTER_RESPONSE = "after_response"
    AFTER_SPOOL = "after_spool"
    DISABLED = "disabled"


class CommitState(str, Enum):
    """
    Logical lifecycle state of a consumed command.
    """

    RECEIVED = "received"
    EXECUTING = "executing"
    EXECUTED = "executed"
    RESPONSE_SENT = "response_sent"
    SPOOL_PERSISTED = "spool_persisted"
    ACKED = "acked"
    FAILED = "failed"


class CommitDecision:
    """
    Result of evaluating whether a Kafka offset may be committed.

    This is transport-independent at decision level.
    Actual Kafka commit operation remains in Kafka adapter/transport.
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
    Tracks logical lifecycle + commit metadata of one consumed command.

    The tracker does NOT:
        - call Kafka
        - commit offsets
        - retry commands
        - execute commands
        - persist state by itself

    It records enough state for KafkaCommitPolicy to decide safely.
    """

    def __init__(
        self,
        command_id: str,
        *,
        commit_ref: Optional[Any] = None,
    ) -> None:
        if not command_id:
            raise ValueError("command_id must not be empty")

        self.command_id = str(command_id)
        self.state = CommitState.RECEIVED

        # Opaque commit reference carried from transport poll result.
        # Examples:
        #   - confluent message object
        #   - {"topic": "...", "partition": 0, "offset": 123}
        #   - any adapter-specific token used later for ack/commit
        self.commit_ref = commit_ref

        self.last_error: Optional[str] = None

    # -----------------------------
    # Lifecycle markers
    # -----------------------------

    def mark_executing(self) -> None:
        self.state = CommitState.EXECUTING

    def mark_executed(self) -> None:
        self.state = CommitState.EXECUTED

    def mark_response_sent(self) -> None:
        self.state = CommitState.RESPONSE_SENT

    def mark_spool_persisted(self) -> None:
        self.state = CommitState.SPOOL_PERSISTED

    def mark_acked(self) -> None:
        self.state = CommitState.ACKED

    def mark_failed(self, error: Optional[str] = None) -> None:
        self.state = CommitState.FAILED
        if error:
            self.last_error = str(error)

    # -----------------------------
    # Helpers
    # -----------------------------

    def can_commit_after_response(self) -> bool:
        return self.state == CommitState.RESPONSE_SENT

    def can_commit_after_spool(self) -> bool:
        return self.state == CommitState.SPOOL_PERSISTED

    @property
    def has_commit_ref(self) -> bool:
        return self.commit_ref is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "state": self.state.value,
            "has_commit_ref": self.has_commit_ref,
            "last_error": self.last_error,
        }


class KafkaCommitPolicy:
    """
    Determines when a Kafka command offset is logically eligible
    for acknowledgement/commit.

    This policy does NOT perform Kafka commit itself.
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

        normalized = str(policy).strip().lower()
        try:
            return CommitPolicy(normalized)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported Kafka commit policy: {policy!r}. "
                f"Supported: {[p.value for p in CommitPolicy]}"
            ) from exc

    @classmethod
    def from_config(
        cls,
        config: Any,
    ) -> "KafkaCommitPolicy":
        """
        Build a policy from configuration.

        Precedence:
            1) kafka.commit_policy (explicit)
            2) kafka.enable_auto_commit (compat fallback)
               True  -> AUTO
               False -> MANUAL
        """
        explicit_policy = None

        try:
            explicit_policy = config.get("kafka.commit_policy", None)
        except AttributeError:
            explicit_policy = None

        if explicit_policy:
            return cls(explicit_policy)

        try:
            auto_commit = config.get("kafka.enable_auto_commit", True)
        except AttributeError:
            auto_commit = True

        return cls(CommitPolicy.AUTO if bool(auto_commit) else CommitPolicy.MANUAL)

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
        if not isinstance(tracker, CommandCommitTracker):
            raise TypeError("tracker must be CommandCommitTracker")

        # Hard-stop guard: without commit reference, ack cannot be executed safely.
        if self.policy in {
            CommitPolicy.MANUAL,
            CommitPolicy.AFTER_RESPONSE,
            CommitPolicy.AFTER_SPOOL,
        } and not tracker.has_commit_ref:
            return CommitDecision(
                allowed=False,
                reason="Missing commit reference for application-managed commit.",
                command_id=tracker.command_id,
                state=tracker.state,
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
                reason="Offset commits are explicitly disabled.",
                command_id=tracker.command_id,
                state=tracker.state,
            )

        if self.policy == CommitPolicy.MANUAL:
            if tracker.state in {CommitState.RECEIVED, CommitState.EXECUTING}:
                return CommitDecision(
                    allowed=False,
                    reason="Command has not completed execution.",
                    command_id=tracker.command_id,
                    state=tracker.state,
                )

            if tracker.state == CommitState.FAILED:
                return CommitDecision(
                    allowed=False,
                    reason="Failed command must not be committed by generic manual policy.",
                    command_id=tracker.command_id,
                    state=tracker.state,
                )

            return CommitDecision(
                allowed=True,
                reason="Manual commit is allowed after command execution completion.",
                command_id=tracker.command_id,
                state=tracker.state,
            )

        if self.policy == CommitPolicy.AFTER_RESPONSE:
            if tracker.state == CommitState.RESPONSE_SENT:
                return CommitDecision(
                    allowed=True,
                    reason="Response has been successfully published.",
                    command_id=tracker.command_id,
                    state=tracker.state,
                )

            return CommitDecision(
                allowed=False,
                reason="Offset cannot be committed before response publication.",
                command_id=tracker.command_id,
                state=tracker.state,
            )

        if self.policy == CommitPolicy.AFTER_SPOOL:
            if tracker.state == CommitState.SPOOL_PERSISTED:
                return CommitDecision(
                    allowed=True,
                    reason="Command/result is durably persisted in spool.",
                    command_id=tracker.command_id,
                    state=tracker.state,
                )

            return CommitDecision(
                allowed=False,
                reason="Offset cannot be committed before spool persistence.",
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
        Convenience method returning only commit decision.
        """
        return bool(self.evaluate(tracker))

    # ------------------------------------------------------------------
    # Runtime information
    # ------------------------------------------------------------------

    @property
    def is_application_managed(self) -> bool:
        return self.policy in {
            CommitPolicy.MANUAL,
            CommitPolicy.AFTER_RESPONSE,
            CommitPolicy.AFTER_SPOOL,
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
