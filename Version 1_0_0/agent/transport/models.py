# Path: agent/transport/models.py

"""Backward-compatible transport model imports.

Canonical domain contracts live in :mod:`agent.contracts`.

This module intentionally contains no model definitions. It only
re-exports the canonical contracts so older transport-layer imports
remain compatible.

Transport implementations should prefer importing these contracts
directly from ``agent.contracts`` when possible.
"""

from __future__ import annotations

from ..contracts.command import CommandEnvelope
from ..contracts.response import ResponseEnvelope, ResponseStatus


__all__ = [
    "CommandEnvelope",
    "ResponseEnvelope",
    "ResponseStatus",
]