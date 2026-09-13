from agent.adapters.mt5_adapter import MT5Adapter
from agent.contracts.models import Status


class Agent:
    """Core agent that manages the MT5 connection lifecycle."""

    def __init__(self, mt5_adapter: MT5Adapter | None = None) -> None:
        self.mt5 = mt5_adapter or MT5Adapter()

    def start(self) -> Status:
        """Start the agent by connecting to MetaTrader 5."""
        if self.mt5.connect():
            return Status(True, "MT5 connection established.")
        return Status(False, "Unable to connect to MT5.")

    def stop(self) -> None:
        self.mt5.disconnect()

    def is_ready(self) -> Status:
        """Return the current MT5 readiness status."""
        if self.mt5.is_connected():
            return Status(True, "Agent is ready.")
        return Status(False, "Agent is not connected to MT5.")
