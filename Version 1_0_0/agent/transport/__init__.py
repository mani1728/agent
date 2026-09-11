# Path: agent/transport/__init__.py

"""Transport layer public API.

This package exposes the transport-independent transport interface and
backward-compatible access to the canonical domain contracts.

Concrete transport implementations such as Kafka or Gateway must not
be imported from this package during the contract/interface foundation
phase.

The goal is to keep the Agent core independent from concrete transport
implementations.
"""

from ..contracts import (
    CommandEnvelope,
    ResponseEnvelope,
)
from .base import ITransportClient


__all__ = [
    # Domain contracts
    "CommandEnvelope",
    "ResponseEnvelope",

    # Transport interface
    "ITransportClient",
]