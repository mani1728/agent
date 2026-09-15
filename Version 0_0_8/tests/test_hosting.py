import threading
import time
import urllib.request

from agent.adapters.http_transport import HTTPTransportAdapter
from agent.application.host import ApplicationHost
from agent.contracts.models import Status
from agent.infrastructure.http_server_host import HTTPServerHost


class FakeAgent:
    def __init__(self, start_ok=True, stop_ok=True, calls=None):
        self.start_ok = start_ok
        self.stop_ok = stop_ok
        self.calls = calls if calls is not None else []

    def start(self):
        self.calls.append("agent.start")
        return Status(self.start_ok, "start", "start")

    def stop(self):
        self.calls.append("agent.stop")
        return Status(self.stop_ok, "stop", "stop")


class FakeHosting:
    def __init__(self, calls=None, error=None):
        self.calls = calls if calls is not None else []
        self.error = error

    def serve(self):
        self.calls.append("hosting.serve")
        if self.error:
            raise self.error

    def shutdown(self):
        self.calls.append("hosting.shutdown")


class EchoApplication:
    def handle(self, request):
        from agent.contracts.transport import TransportResponse
        return TransportResponse(
            request.context.request_id,
            request.context.correlation_id,
            request.command.command_id,
            True,
            "ok",
            "ok",
        )


def test_application_host_orders_start_serve_stop():
    calls = []
    result = ApplicationHost(FakeAgent(calls=calls), FakeHosting(calls=calls)).run()
    assert result.ok
    assert result.code == "stopped"
    assert calls == ["agent.start", "hosting.serve", "agent.stop"]


def test_start_failure_prevents_serving_and_cleanup():
    calls = []
    result = ApplicationHost(FakeAgent(start_ok=False, calls=calls), FakeHosting(calls=calls)).run()
    assert not result.ok
    assert result.code == "agent_start_failed"
    assert calls == ["agent.start"]


def test_hosting_failure_still_stops_agent_and_remains_primary_failure():
    calls = []
    result = ApplicationHost(
        FakeAgent(stop_ok=False, calls=calls),
        FakeHosting(calls=calls, error=OSError("bind failed")),
    ).run()
    assert not result.ok
    assert result.code == "hosting_failed"
    assert calls == ["agent.start", "hosting.serve", "agent.stop"]


def test_stop_failure_is_reported_after_normal_serving():
    result = ApplicationHost(FakeAgent(stop_ok=False), FakeHosting()).run()
    assert not result.ok
    assert result.code == "agent_stop_failed"


def test_http_server_host_serves_and_shuts_down_cleanly():
    transport = HTTPTransportAdapter(EchoApplication())
    server = transport.create_server("127.0.0.1", 0)
    port = server.server_address[1]
    hosting = HTTPServerHost(lambda: server)
    thread = threading.Thread(target=hosting.serve)
    thread.start()
    try:
        deadline = time.time() + 5
        response = None
        body = (
            b'{"request_id":"r1","correlation_id":"c1","command":'
            b'{"command_id":"cmd1","command_type":"agent.get_status","schema_version":"1.0",'
            b'"correlation_id":"c1","timestamp":"2026-01-01T00:00:00Z","payload":{}}}'
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/command",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        while time.time() < deadline:
            try:
                response = urllib.request.urlopen(request, timeout=0.5)
                break
            except OSError:
                time.sleep(0.05)
        assert response is not None
        assert response.status == 200
    finally:
        hosting.shutdown()
        thread.join(timeout=5)
    assert not thread.is_alive()
