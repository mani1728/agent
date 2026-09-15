"""Concrete standard-library HTTP hosting adapter."""

from __future__ import annotations

from http.server import ThreadingHTTPServer


class HTTPServerHost:
    """Own the concrete HTTP server lifecycle behind HostingPort semantics."""

    def __init__(self, server: ThreadingHTTPServer) -> None:
        self._server = server
        self._closed = False

    def serve(self) -> None:
        """Block while serving and always release the listening socket on exit."""
        try:
            self._server.serve_forever()
        finally:
            self._close()

    def shutdown(self) -> None:
        """Request graceful termination of serve_forever."""
        self._server.shutdown()

    def _close(self) -> None:
        if not self._closed:
            self._server.server_close()
            self._closed = True
