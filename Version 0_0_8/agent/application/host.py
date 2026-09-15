"""Application-level hosting lifecycle coordination."""

from __future__ import annotations

import logging

from agent.contracts.models import Status
from agent.contracts.ports import AgentLifecyclePort, HostingPort


class ApplicationHost:
    """Coordinate Agent lifecycle with a transport-neutral blocking host.

    The coordinator owns ordering only. It has no knowledge of HTTP servers,
    sockets, operating-system signals, or concrete MT5 infrastructure.
    """

    def __init__(
        self,
        agent: AgentLifecyclePort,
        hosting: HostingPort,
        logger: logging.Logger | None = None,
    ) -> None:
        self._agent = agent
        self._hosting = hosting
        self._logger = logger or logging.getLogger(__name__)

    def run(self) -> Status:
        """Start the Agent, serve until termination, then stop the Agent.

        Startup, hosting, and shutdown exceptions are contained at this boundary.
        A hosting failure remains primary when cleanup also fails.
        """
        try:
            start_status = self._agent.start()
        except Exception:
            self._logger.exception("Agent startup failed")
            return Status(False, "Agent startup failed.", "agent_start_failed")
        if not start_status.ok:
            return Status(False, start_status.message, "agent_start_failed")

        primary_failure: Status | None = None
        try:
            self._hosting.serve()
        except Exception:
            self._logger.exception("Hosting failed")
            primary_failure = Status(False, "Application hosting failed.", "hosting_failed")
        finally:
            try:
                stop_status = self._agent.stop()
            except Exception:
                self._logger.exception("Agent cleanup failed")
                stop_status = Status(False, "Agent cleanup failed.", "agent_stop_failed")
            if not stop_status.ok:
                if primary_failure is not None:
                    self._logger.error("Agent cleanup failed after hosting failure: %s", stop_status.message)
                else:
                    primary_failure = Status(False, stop_status.message, "agent_stop_failed")

        return primary_failure or Status(True, "Application host stopped.", "stopped")
