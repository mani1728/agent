import threading
import time
import urllib.request

from agent.adapters.http_transport import HTTPTransportAdapter
from agent.application.host import ApplicationHost
from agent.contracts.models import Status
from agent.contracts.operational_observability import OperationalEventType
from agent.infrastructure.http_server_host import HTTPServerHost


class FakeAgent:
    def __init__(self, start_ok=True, stop_ok=True, calls=None, start_error=None, stop_error=None):
        self.start_ok = start_ok
        self.stop_ok = stop_ok
        self.calls = calls if calls is not None else []
        self.start_error = start_error
        self.stop_error = stop_error

    def start(self):
        self.calls.append("agent.start")
        if self.start_error:
            raise self.start_error
        return Status(self.start_ok, "start", "start")

    def stop(self):
        self.calls.append("agent.stop")
        if self.stop_error:
            raise self.stop_error
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


class RecordingOperationalObservability:
    def __init__(self, error=None):
        self.events = []
        self.error = error

    def record(self, event):
        if self.error:
            raise self.error
        self.events.append(event)


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


def test_successful_lifecycle_emits_ordered_operational_events():
    observer = RecordingOperationalObservability()
    result = ApplicationHost(
        FakeAgent(),
        FakeHosting(),
        operational_observability=observer,
    ).run()

    assert result.ok
    assert [event.event_type for event in observer.events] == [
        OperationalEventType.APPLICATION_STARTING,
        OperationalEventType.APPLICATION_STARTED,
        OperationalEventType.HOSTING_STARTED,
        OperationalEventType.APPLICATION_STOPPING,
        OperationalEventType.APPLICATION_STOPPED,
    ]
    assert all(event.source == "ApplicationHost" for event in observer.events)


def test_start_failure_prevents_serving_and_cleanup():
    calls = []
    observer = RecordingOperationalObservability()
    result = ApplicationHost(
        FakeAgent(start_ok=False, calls=calls),
        FakeHosting(calls=calls),
        operational_observability=observer,
    ).run()
    assert not result.ok
    assert result.code == "agent_start_failed"
    assert calls == ["agent.start"]
    assert [event.event_type for event in observer.events] == [
        OperationalEventType.APPLICATION_STARTING,
        OperationalEventType.APPLICATION_START_FAILED,
    ]


def test_start_exception_is_contained_and_prevents_serving():
    calls = []
    observer = RecordingOperationalObservability()
    result = ApplicationHost(
        FakeAgent(calls=calls, start_error=RuntimeError("start exploded")),
        FakeHosting(calls=calls),
        operational_observability=observer,
    ).run()
    assert not result.ok
    assert result.code == "agent_start_failed"
    assert result.message == "Agent startup failed."
    assert calls == ["agent.start"]
    assert observer.events[-1].event_type == OperationalEventType.APPLICATION_START_FAILED


def test_hosting_failure_still_stops_agent_and_remains_primary_failure():
    calls = []
    observer = RecordingOperationalObservability()
    result = ApplicationHost(
        FakeAgent(stop_ok=False, calls=calls),
        FakeHosting(calls=calls, error=OSError("bind failed")),
        operational_observability=observer,
    ).run()
    assert not result.ok
    assert result.code == "hosting_failed"
    assert calls == ["agent.start", "hosting.serve", "agent.stop"]
    assert [event.event_type for event in observer.events][-3:] == [
        OperationalEventType.HOSTING_FAILED,
        OperationalEventType.APPLICATION_STOPPING,
        OperationalEventType.APPLICATION_STOP_FAILED,
    ]


def test_hosting_failure_remains_primary_when_stop_raises():
    calls = []
    result = ApplicationHost(
        FakeAgent(calls=calls, stop_error=RuntimeError("stop exploded")),
        FakeHosting(calls=calls, error=OSError("bind failed")),
    ).run()
    assert not result.ok
    assert result.code == "hosting_failed"
    assert calls == ["agent.start", "hosting.serve", "agent.stop"]


def test_stop_failure_is_reported_after_normal_serving():
    observer = RecordingOperationalObservability()
    result = ApplicationHost(
        FakeAgent(stop_ok=False),
        FakeHosting(),
        operational_observability=observer,
    ).run()
    assert not result.ok
    assert result.code == "agent_stop_failed"
    assert observer.events[-1].event_type == OperationalEventType.APPLICATION_STOP_FAILED


def test_stop_exception_is_contained_after_normal_serving():
    result = ApplicationHost(
        FakeAgent(stop_error=RuntimeError("stop exploded")),
        FakeHosting(),
    ).run()
    assert not result.ok
    assert result.code == "agent_stop_failed"
    assert result.message == "Agent cleanup failed."


def test_operational_observer_failure_does_not_change_lifecycle_result():
    observer = RecordingOperationalObservability(error=RuntimeError("observer unavailable"))
    result = ApplicationHost(
        FakeAgent(),
        FakeHosting(),
        operational_observability=observer,
    ).run()

    assert result.ok
    assert result.code == "stopped"


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
