import MetaTrader5 as mt5


class MT5Adapter:
    """Minimal adapter for connecting to the MetaTrader 5 terminal."""

    def connect(self) -> bool:
        """Initialize the MetaTrader 5 connection."""
        return mt5.initialize()

    def disconnect(self) -> None:
        """Close the MetaTrader 5 connection."""
        mt5.shutdown()

    def is_connected(self) -> bool:
        """Return True when the MetaTrader 5 terminal is reachable."""
        return mt5.terminal_info() is not None
