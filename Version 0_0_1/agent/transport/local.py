from agent.contracts.models import Status


class LocalTransport:
    """Minimal local transport for reporting agent status."""

    @staticmethod
    def send(status: Status) -> None:
        print(status.message)
