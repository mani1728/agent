from dataclasses import dataclass


@dataclass(frozen=True)
class Status:
    """Simple status contract used by the agent."""

    ok: bool
    message: str = ""
