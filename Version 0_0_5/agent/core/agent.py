import logging

from agent.contracts.models import AgentConfig, HealthStatus, LifecycleState, Status
from agent.contracts.ports import MT5Port


class Agent:
    """Own the runtime lifecycle while depending only on the MT5 port."""

    def __init__(self, mt5_adapter: MT5Port, config: AgentConfig | None = None, logger: logging.Logger | None = None) -> None:
        self.config = config or AgentConfig()
        self.logger = logger or logging.getLogger(__name__)
        self.mt5 = mt5_adapter
        self._state = LifecycleState.CREATED

    @property
    def state(self) -> LifecycleState:
        return self._state

    def start(self) -> Status:
        if self._state is LifecycleState.RUNNING:
            return Status(True, "Agent is already running.", "already_running")
        if self._state in (LifecycleState.STARTING, LifecycleState.STOPPING):
            return Status(False, "Agent is busy with another lifecycle transition.", "lifecycle_busy")
        self._state = LifecycleState.STARTING
        self.logger.info("Starting %s", self.config.app_name)
        try:
            connected = bool(self.mt5.connect())
        except Exception:
            self.logger.exception("MT5 adapter connection failed")
            connected = False
        if connected:
            self._state = LifecycleState.RUNNING
            return Status(True, "MT5 connection established.", "connected")
        self._state = LifecycleState.FAILED
        return Status(False, "Unable to connect to MT5.", "connection_failed")

    def stop(self) -> Status:
        if self._state is LifecycleState.STOPPING:
            return Status(False, "Agent is already stopping.", "lifecycle_busy")
        self._state = LifecycleState.STOPPING
        try:
            disconnected = bool(self.mt5.disconnect())
        except Exception:
            self.logger.exception("MT5 adapter disconnect failed")
            disconnected = False
        if not disconnected:
            self._state = LifecycleState.FAILED
            return Status(False, "Unable to stop the agent cleanly.", "disconnect_failed")
        self._state = LifecycleState.STOPPED
        return Status(True, "Agent stopped.", "stopped")

    def health(self) -> HealthStatus:
        if self._state is not LifecycleState.RUNNING:
            return HealthStatus(False, self._state, f"Agent is not running ({self._state.value}).")
        try:
            connected = bool(self.mt5.is_connected())
        except Exception:
            self.logger.exception("MT5 health probe failed")
            connected = False
        if connected:
            return HealthStatus(True, self._state, "Agent is healthy.")
        return HealthStatus(False, self._state, "Agent is running but MT5 is not connected.")

    def is_ready(self) -> Status:
        health = self.health()
        return Status(health.ok, health.message, "healthy" if health.ok else "not_ready")
