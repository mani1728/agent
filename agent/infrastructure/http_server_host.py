"""Concrete standard-library HTTP hosting adapter."""

from __future__ import annotations

import threading
import logging
from collections.abc import Callable
from http.server import ThreadingHTTPServer
from agent.infrastructure.logging_observability import safe_log


class HTTPServerHost:
    """Own the concrete HTTP server lifecycle behind HostingPort semantics."""

    def __init__(self, server_factory: Callable[[], ThreadingHTTPServer]) -> None:
        self._server_factory = server_factory
        self._server: ThreadingHTTPServer | None = None
        self._lock = threading.Lock()
        self._shutdown_requested = False

    def serve(self) -> None:
        """Create, bind, and serve until shutdown, then release the socket."""
        server = self._server_factory()
        with self._lock:
            self._server = server
            shutdown_requested = self._shutdown_requested
        if shutdown_requested:
            server.server_close()
            return
        try:
            safe_log(logging.getLogger(__name__), logging.INFO,
                     "HTTP host listening on %s:%s", *server.server_address[:2])
            server.serve_forever()
        finally:
            server.server_close()
            with self._lock:
                self._server = None

    def shutdown(self) -> None:
        """Request graceful termination of the active or next serving loop."""
        safe_log(logging.getLogger(__name__), logging.INFO, "Shutdown requested")
        with self._lock:
            self._shutdown_requested = True
            server = self._server
        if server is not None:
            server.shutdown()
