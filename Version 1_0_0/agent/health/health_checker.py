# Path: Version 1_0_0/agent/health/health_checker.py

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Optional


class HealthStatus(str, Enum):
    """Overall health state of a component or service."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class HealthCheckResult:
    """Result returned by a single health check."""

    name: str
    status: HealthStatus
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    @property
    def degraded(self) -> bool:
        return self.status == HealthStatus.DEGRADED

    @property
    def unhealthy(self) -> bool:
        return self.status == HealthStatus.UNHEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": dict(self.details),
            "duration_ms": round(self.duration_ms, 3),
        }


HealthCheckCallable = Callable[[], Any]


class HealthChecker:
    """
    Registry and executor for application health checks.

    Checks are intentionally independent from transport, persistence,
    retry and business execution layers.
    """

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._checks: dict[str, HealthCheckCallable] = {}

    def register(
        self,
        name: str,
        check: HealthCheckCallable,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("health check name must be non-empty")

        if not callable(check):
            raise TypeError("health check must be callable")

        self._checks[name.strip()] = check

    def unregister(self, name: str) -> bool:
        return self._checks.pop(name, None) is not None

    def has(self, name: str) -> bool:
        return name in self._checks

    def names(self) -> tuple[str, ...]:
        return tuple(self._checks.keys())

    def check(self, name: str) -> HealthCheckResult:
        if name not in self._checks:
            raise KeyError(f"health check not registered: {name}")

        return self._execute(name, self._checks[name])

    def check_all(self) -> list[HealthCheckResult]:
        return [
            self._execute(name, check)
            for name, check in self._checks.items()
        ]

    def overall_status(
        self,
        results: Iterable[HealthCheckResult],
    ) -> HealthStatus:
        results = list(results)

        if not results:
            return HealthStatus.HEALTHY

        if any(
            result.status == HealthStatus.UNHEALTHY
            for result in results
        ):
            return HealthStatus.UNHEALTHY

        if any(
            result.status == HealthStatus.DEGRADED
            for result in results
        ):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def check_all_dict(self) -> dict[str, Any]:
        results = self.check_all()
        status = self.overall_status(results)

        return {
            "status": status.value,
            "healthy": status == HealthStatus.HEALTHY,
            "checks": {
                result.name: result.to_dict()
                for result in results
            },
        }

    def clear(self) -> None:
        self._checks.clear()

    def _execute(
        self,
        name: str,
        check: HealthCheckCallable,
    ) -> HealthCheckResult:
        started = time.monotonic()

        try:
            raw_result = check()

            status, message, details = self._normalize_result(raw_result)

            return HealthCheckResult(
                name=name,
                status=status,
                message=message,
                details=details,
                duration_ms=(time.monotonic() - started) * 1000.0,
            )

        except Exception as exc:
            duration_ms = (time.monotonic() - started) * 1000.0

            self._logger.exception(
                "Health check failed: %s",
                name,
            )

            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(exc) or exc.__class__.__name__,
                details={
                    "exception": exc.__class__.__name__,
                },
                duration_ms=duration_ms,
            )

    @staticmethod
    def _normalize_result(
        result: Any,
    ) -> tuple[
        HealthStatus,
        str,
        Mapping[str, Any],
    ]:
        if isinstance(result, HealthCheckResult):
            return (
                result.status,
                result.message,
                result.details,
            )

        if isinstance(result, bool):
            return (
                HealthStatus.HEALTHY
                if result
                else HealthStatus.UNHEALTHY,
                "",
                {},
            )

        if result is None:
            return HealthStatus.HEALTHY, "", {}

        if isinstance(result, Mapping):
            raw_status = result.get(
                "status",
                HealthStatus.HEALTHY.value,
            )

            try:
                status = (
                    raw_status
                    if isinstance(raw_status, HealthStatus)
                    else HealthStatus(str(raw_status).lower())
                )
            except ValueError:
                status = HealthStatus.UNHEALTHY

            message = str(result.get("message", ""))

            details = result.get("details", {})
            if not isinstance(details, Mapping):
                details = {"value": details}

            return status, message, dict(details)

        return (
            HealthStatus.HEALTHY,
            "",
            {"value": result},
        )


__all__ = [
    "HealthCheckCallable",
    "HealthCheckResult",
    "HealthChecker",
    "HealthStatus",
]