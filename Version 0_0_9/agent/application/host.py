"""Application-level hosting lifecycle coordination."""

from __future__ import annotations

import logging
from uuid import uuid4

from agent.contracts.models import Status
from agent.contracts.operational_observability import (
    NullOperationalObservability,
    OperationalEvent,
    OperationalEventType,
    OperationalObservabilityPort,
)
from agent.contracts.ports import AgentLifecyclePort, HostingPort


class ApplicationHost:
    """Coordinate Agent lifecycle with a transport-neutral blocking host.

    The coordinator owns ordering only. It has no knowledge of HTTP servers,
    sockets, operating-system signals, or concrete MT5 infrastructure.
    Operational observability is best-effort and cannot alter lifecycle results.
    """

    def __init__(
        self,
        agent: AgentLifecyclePort,
        hosting: HostingPort,
        logger: logging.Logger | None = None,
        operational_observability: OperationalObservabilityPort | None = None,
    ) -> None:
        self._agent = agent
        self._hosting = hosting
        self._logger = logger or logging.getLogger(__name__)
        self._operational_observability = operational_observability or NullOperationalObservability()

    def _record(
        self,
        event_type: OperationalEventType,
        outcome: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Record an operational event without affecting lifecycle execution."""
        try:
            self._operational_observability.record(
                OperationalEvent.now(
                    event_id=str(uuid4()),
                    event_type=event_type,
                    source="ApplicationHost",
                    outcome=outcome,
                    metadata=metadata,
                )
            )
        except Exception:
            self._logger.exception("Operational observability failed")

    def run(self) -> Status:
        """Start the Agent, serve until termination, then stop the Agent.

        Startup, hosting, and shutdown exceptions are contained at this boundary.
        A hosting failure remains primary when cleanup also fails.
        """
        self._record(OperationalEventType.APPLICATION_STARTING, "started")
        try:
            start_status = self._agent.start()
        except Exception:
            self._logger.exception("Agent startup failed")
            self._record(OperationalEventType.APPLICATION_START_FAILED, "failed")
            return Status(False, "Agent startup failed.", "agent_start_failed")
        if not start_status.ok:
            self._record(
                OperationalEventType.APPLICATION_START_FAILED,
                "failed",
                {"code": start_status.code},
            )
            return Status(False, start_status.message, "agent_start_failed")

        self._record(OperationalEventType.APPLICATION_STARTED, "success")
        primary_failure: Status | None = None
        try:
            self._record(OperationalEventType.HOSTING_STARTED, "started")
            self._hosting.serve()
        except Exception:
            self._logger.exception("Hosting failed")
            self._record(OperationalEventType.HOSTING_FAILED, "failed")
            primary_failure = Status(False, "Application hosting failed.", "hosting_failed")
        finally:
            self._record(OperationalEventType.APPLICATION_STOPPING, "started")
            try:
                stop_status = self._agent.stop()
            except Exception:
                self._logger.exception("Agent cleanup failed")
                self._record(OperationalEventType.APPLICATION_STOP_FAILED, "failed")
                stop_status = Status(False, "Agent cleanup failed.", "agent_stop_failed")
            if not stop_status.ok:
                if stop_status.message != "Agent cleanup failed.":
                    self._record(
                        OperationalEventType.APPLICATION_STOP_FAILED,
                        "failed",
                        {"code": stop_status.code},
                    )
                if primary_failure is not None:
                    self._logger.error("Agent cleanup failed after hosting failure: %s", stop_status.message)
                else:
                    primary_failure = Status(False, stop_status.message, "agent_stop_failed")
            else:
                self._record(OperationalEventType.APPLICATION_STOPPED, "success")

        return primary_failure or Status(True, "Application host stopped.", "stopped")
