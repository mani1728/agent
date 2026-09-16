from typing import cast

import pytest

from agent.contracts.operational_observability import (
    NullOperationalObservability,
    OperationalEvent,
    OperationalEventType,
    OperationalObservabilityPort,
)


def test_operational_event_creation():
    event = OperationalEvent.now(
        event_id="event-1",
        event_type=OperationalEventType.APPLICATION_STARTED,
        source="ApplicationHost",
        outcome="success",
        metadata={"component": "host"},
    )

    assert event.event_type == OperationalEventType.APPLICATION_STARTED
    assert event.source == "ApplicationHost"
    assert event.metadata["component"] == "host"


def test_operational_event_is_immutable():
    event = OperationalEvent.now(
        "event-1",
        OperationalEventType.APPLICATION_STARTED,
        "ApplicationHost",
        "success",
        {"component": "host"},
    )

    with pytest.raises(TypeError):
        event.metadata["new"] = "value"

    with pytest.raises(Exception):
        event.source = "changed"


def test_operational_event_type_values():
    assert OperationalEventType.APPLICATION_STARTED.value == "application_started"
    assert OperationalEventType.APPLICATION_STOPPED.value == "application_stopped"


def test_null_operational_observability_implements_port():
    observer = NullOperationalObservability()

    assert isinstance(observer, OperationalObservabilityPort)

    event = OperationalEvent.now(
        "event-1",
        OperationalEventType.APPLICATION_STARTED,
        "ApplicationHost",
        "success",
    )

    assert observer.record(event) is None


def test_invalid_required_fields_are_rejected():
    with pytest.raises(ValueError):
        OperationalEvent(
            "",
            OperationalEventType.APPLICATION_STARTED,
            "timestamp",
            "ApplicationHost",
            "success",
            {},
        )
