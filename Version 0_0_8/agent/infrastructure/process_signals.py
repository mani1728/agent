"""Process-signal adapter for graceful hosting shutdown."""

from __future__ import annotations

import signal
import threading
from collections.abc import Callable


def install_shutdown_signal_handlers(shutdown: Callable[[], None]) -> None:
    """Translate supported process termination signals into host shutdown.

    shutdown is invoked on a separate daemon thread because Python's
    BaseServer.shutdown() must not run on the serve_forever() thread.
    """

    def handle_signal(signum: int, frame: object) -> None:
        del signum, frame
        threading.Thread(target=shutdown, name="agent-host-shutdown", daemon=True).start()

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)
