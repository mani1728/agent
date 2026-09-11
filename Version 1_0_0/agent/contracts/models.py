# Path: agent/contracts/models.py

"""Shared primitive types used across domain contracts.

Keeping primitive types in this module avoids circular imports between
command.py, response.py, and heartbeat.py.

This module must remain transport-independent.
"""

from __future__ import annotations

from typing import Any


# A plain JSON-serialisable mapping used for:
# - command params
# - command metadata
# - response data
# - heartbeat details
JsonDict = dict[str, Any]


__all__ = [
    "JsonDict",
]