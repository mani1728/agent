# Path: Version 1_0_0/agent/adapters/mt5_adapter.py

"""MetaTrader 5 adapter.

This module provides the architectural boundary between the application
core and the legacy Mt5_Manager implementation.

The adapter intentionally delegates MT5 operations to Mt5_Manager instead
of duplicating or rewriting the existing trading logic.

Responsibilities
----------------
- Expose a stable MT5 adapter boundary.
- Delegate supported operations to Mt5_Manager.
- Keep MetaTrader5 implementation details outside the core layer.
- Preserve existing Mt5_Manager behavior during migration.

This module does not implement:
- command dispatch
- transport
- retry
- persistence
- authentication
- authorization
- worker lifecycle
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from agent.core.meta_trader_manager import Mt5_Manager


class Mt5Adapter:
    """Application-facing adapter around the existing Mt5_Manager."""

    def __init__(
        self,
        manager: Optional[Mt5_Manager] = None,
    ) -> None:
        self._manager = manager or Mt5_Manager()

    @property
    def manager(self) -> Mt5_Manager:
        """Return the underlying MT5 manager.

        This property is intentionally exposed for compatibility and
        migration scenarios where existing code still needs direct access.
        """
        return self._manager

    # ------------------------------------------------------------------
    # Generic delegation
    # ------------------------------------------------------------------

    def execute(
        self,
        method_name: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        """Execute a supported Mt5_Manager method.

        The adapter performs only method-name validation and delegation.
        Business behavior remains inside Mt5_Manager.
        """
        if not isinstance(method_name, str) or not method_name.strip():
            raise ValueError(
                "method_name must be a non-empty string"
            )

        method = getattr(
            self._manager,
            method_name.strip(),
            None,
        )

        if method is None or not callable(method):
            raise AttributeError(
                f"Mt5_Manager does not expose callable method "
                f"{method_name!r}"
            )

        if params is None:
            return method()

        if not isinstance(params, Mapping):
            raise TypeError(
                "params must be a mapping or None"
            )

        return method(**dict(params))

    # ------------------------------------------------------------------
    # Explicit MT5 operation boundaries
    # ------------------------------------------------------------------

    def manage_connection(
        self,
        **params: Any,
    ) -> Any:
        """Delegate connection management to Mt5_Manager."""
        return self._manager.manage_connection(**params)

    def manage_symbols(
        self,
        **params: Any,
    ) -> Any:
        """Delegate symbol management to Mt5_Manager."""
        return self._manager.manage_symbols(**params)

    def manage_market_book(
        self,
        **params: Any,
    ) -> Any:
        """Delegate market-book operations to Mt5_Manager."""
        return self._manager.manage_market_book(**params)

    def fetch_data(
        self,
        **params: Any,
    ) -> Any:
        """Delegate market-data retrieval to Mt5_Manager."""
        return self._manager.fetch_data(**params)

    def trade_manager(
        self,
        **params: Any,
    ) -> Any:
        """Delegate trading operations to Mt5_Manager."""
        return self._manager.trade_manager(**params)

    def manage_positions_history(
        self,
        **params: Any,
    ) -> Any:
        """Delegate positions/history operations to Mt5_Manager."""
        return self._manager.manage_positions_history(**params)

    # ------------------------------------------------------------------
    # Lifecycle compatibility
    # ------------------------------------------------------------------

    def shutdown(self) -> Any:
        """Shutdown MT5 through the existing manager.

        The actual MT5 shutdown behavior remains owned by Mt5_Manager.
        """
        return self._manager.manage_connection(
            action="shutdown",
        )


__all__ = [
    "Mt5Adapter",
]