from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class MetricSnapshot:
    """Immutable snapshot of a metric."""

    name: str
    value: float
    metric_type: str
    labels: Mapping[str, str]
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type,
            "labels": dict(self.labels),
            "timestamp": self.timestamp,
        }


class Counter:
    """Monotonically increasing metric."""

    def __init__(
        self,
        name: str,
        *,
        labels: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._validate_name(name)

        self.name = name
        self.labels = dict(labels or {})
        self._value = 0.0
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0) -> float:
        amount = float(amount)

        if amount < 0:
            raise ValueError("counter increment cannot be negative")

        with self._lock:
            self._value += amount
            return self._value

    def value(self) -> float:
        with self._lock:
            return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = 0.0

    def snapshot(self) -> MetricSnapshot:
        return MetricSnapshot(
            name=self.name,
            value=self.value(),
            metric_type="counter",
            labels=self.labels,
            timestamp=time.time(),
        )

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("metric name must be non-empty")


class Gauge:
    """Metric representing a value that can increase or decrease."""

    def __init__(
        self,
        name: str,
        *,
        labels: Optional[Mapping[str, str]] = None,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("metric name must be non-empty")

        self.name = name
        self.labels = dict(labels or {})
        self._value = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> float:
        with self._lock:
            self._value = float(value)
            return self._value

    def inc(self, amount: float = 1.0) -> float:
        with self._lock:
            self._value += float(amount)
            return self._value

    def dec(self, amount: float = 1.0) -> float:
        with self._lock:
            self._value -= float(amount)
            return self._value

    def value(self) -> float:
        with self._lock:
            return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = 0.0

    def snapshot(self) -> MetricSnapshot:
        return MetricSnapshot(
            name=self.name,
            value=self.value(),
            metric_type="gauge",
            labels=self.labels,
            timestamp=time.time(),
        )


class Histogram:
    """
    Simple in-memory histogram.

    It records observations and exposes count, sum, minimum,
    maximum and average. Bucket aggregation is intentionally
    omitted from this infrastructure-level implementation.
    """

    def __init__(
        self,
        name: str,
        *,
        labels: Optional[Mapping[str, str]] = None,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("metric name must be non-empty")

        self.name = name
        self.labels = dict(labels or {})

        self._count = 0
        self._sum = 0.0
        self._minimum: Optional[float] = None
        self._maximum: Optional[float] = None

        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        value = float(value)

        with self._lock:
            self._count += 1
            self._sum += value

            if self._minimum is None or value < self._minimum:
                self._minimum = value

            if self._maximum is None or value > self._maximum:
                self._maximum = value

    def count(self) -> int:
        with self._lock:
            return self._count

    def total(self) -> float:
        with self._lock:
            return self._sum

    def minimum(self) -> Optional[float]:
        with self._lock:
            return self._minimum

    def maximum(self) -> Optional[float]:
        with self._lock:
            return self._maximum

    def average(self) -> float:
        with self._lock:
            if self._count == 0:
                return 0.0

            return self._sum / self._count

    def reset(self) -> None:
        with self._lock:
            self._count = 0
            self._sum = 0.0
            self._minimum = None
            self._maximum = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "type": "histogram",
                "labels": dict(self.labels),
                "count": self._count,
                "sum": self._sum,
                "min": self._minimum,
                "max": self._maximum,
                "average": (
                    self._sum / self._count
                    if self._count
                    else 0.0
                ),
                "timestamp": time.time(),
            }


class MetricsRegistry:
    """
    Thread-safe registry for application metrics.

    The registry is intentionally lightweight and does not depend
    on Prometheus, OpenTelemetry, Kafka, HTTP or any other transport.
    """

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = threading.RLock()

    def counter(
        self,
        name: str,
        *,
        labels: Optional[Mapping[str, str]] = None,
    ) -> Counter:
        with self._lock:
            metric = self._counters.get(name)

            if metric is None:
                metric = Counter(name, labels=labels)
                self._counters[name] = metric

            return metric

    def gauge(
        self,
        name: str,
        *,
        labels: Optional[Mapping[str, str]] = None,
    ) -> Gauge:
        with self._lock:
            metric = self._gauges.get(name)

            if metric is None:
                metric = Gauge(name, labels=labels)
                self._gauges[name] = metric

            return metric

    def histogram(
        self,
        name: str,
        *,
        labels: Optional[Mapping[str, str]] = None,
    ) -> Histogram:
        with self._lock:
            metric = self._histograms.get(name)

            if metric is None:
                metric = Histogram(name, labels=labels)
                self._histograms[name] = metric

            return metric

    def get_counter(self, name: str) -> Optional[Counter]:
        with self._lock:
            return self._counters.get(name)

    def get_gauge(self, name: str) -> Optional[Gauge]:
        with self._lock:
            return self._gauges.get(name)

    def get_histogram(self, name: str) -> Optional[Histogram]:
        with self._lock:
            return self._histograms.get(name)

    def snapshots(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": {
                    name: metric.snapshot().to_dict()
                    for name, metric in self._counters.items()
                },
                "gauges": {
                    name: metric.snapshot().to_dict()
                    for name, metric in self._gauges.items()
                },
                "histograms": {
                    name: metric.snapshot()
                    for name, metric in self._histograms.items()
                },
            }

    def reset(self) -> None:
        with self._lock:
            for metric in self._counters.values():
                metric.reset()

            for metric in self._gauges.values():
                metric.reset()

            for metric in self._histograms.values():
                metric.reset()

    def clear(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    def __len__(self) -> int:
        with self._lock:
            return (
                len(self._counters)
                + len(self._gauges)
                + len(self._histograms)
            )


__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "MetricSnapshot",
    "MetricsRegistry",
]