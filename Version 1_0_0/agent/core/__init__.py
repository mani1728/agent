# Path: Version 1_0_0/agent/core/__init__.py
"""
Core application layer.

The core package contains transport-independent command processing
and business execution components.

Concrete transports such as Kafka or HTTP must not be imported from
this package initializer.
"""

from __future__ import annotations

__all__: list[str] = []