from agent.adapters.mt5_adapter import MT5Adapter


class Agent:
    """Core agent that manages the MT5 connection lifecycle."""

    def __init__(self, mt5_adapter: MT5Adapter | None = None) -> None:
        self.mt5 = mt5_adapter or MT5Adapter()

    def start(self) -> bool:
        """Start the agent by connecting to MetaTrader 5."""
        return self.mt5.connect()

    def stop(self) -> None:
        """Stop the agent and close the MT5 connection."""
        self.mt5.disconnect()

    def is_ready(self) -> bool:
        """Return True when the MT5 terminal is connected."""
        return self.mt5.is_connected()
