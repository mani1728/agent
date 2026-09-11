from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Optional


class ReadinessStatus(str, Enum):
    READY = "ready"
    NOT_READY = "not_ready"


@dataclass(frozen=True)
class ReadinessResult:
    status: ReadinessStatus
    message: str = ""
    checks: Mapping[str, bool] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.status == ReadinessStatus.READY

    @property
    def not_ready(self) -> bool:
        return not self.ready

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "ready": self.ready,
            "message": self.message,
            "checks": dict(self.checks),
            "details": dict(self.details),
        }


ReadinessCheck = Callable[[], Any]


class ReadinessChecker:
    """
    Evaluates whether the agent is ready to accept normal work.

    Readiness is intentionally separate from liveness/health:
    a process may be alive while still not being ready to execute commands.
    """

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._checks: dict[str, ReadinessCheck] = {}

    def register(
        self,
        name: str,
        check: ReadinessCheck,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("readiness check name must be non-empty")

        if not callable(check):
            raise TypeError("readiness check must be callable")

        self._checks[name.strip()] = check

    def unregister(self, name: str) -> bool:
        return self._checks.pop(name, None) is not None

    def has(self, name: str) -> bool:
        return name in self._checks

    def names(self) -> tuple[str, ...]:
        return tuple(self._checks.keys())

    def check(self, name: str) -> bool:
        if name not in self._checks:
            raise KeyError(f"readiness check not registered: {name}")

        return self._evaluate(name, self._checks[name])

    def check_all(self) -> ReadinessResult:
        results: dict[str, bool] = {}

        for name, check in self._checks.items():
            results[name] = self._evaluate(name, check)

        ready = all(results.values()) if results else True

        return ReadinessResult(
            status=(
                ReadinessStatus.READY
                if ready
                else ReadinessStatus.NOT_READY
            ),
            message=(
                "agent is ready"
                if ready
                else "one or more readiness checks failed"
            ),
            checks=results,
        )

    def is_ready(self) -> bool:
        return self.check_all().ready

    def require_ready(self) -> None:
        result = self.check_all()

        if not result.ready:
            failed = [
                name
                for name, passed in result.checks.items()
                if not passed
            ]

            raise RuntimeError(
                "agent is not ready"
                + (
                    f": {', '.join(failed)}"
                    if failed
                    else ""
                )
            )

    def clear(self) -> None:
        self._checks.clear()

    def _evaluate(
        self,
        name: str,
        check: ReadinessCheck,
    ) -> bool:
        try:
            result = check()

            if isinstance(result, ReadinessResult):
                return result.ready

            if isinstance(result, Mapping):
                if "ready" in result:
                    return bool(result["ready"])

                if "status" in result:
                    return str(result["status"]).lower() == (
                        ReadinessStatus.READY.value
                    )

                return all(bool(value) for value in result.values())

            return bool(result)

        except Exception:
            self._logger.exception(
                "Readiness check failed: %s",
                name,
            )
            return False


def all_ready(
    checks: Iterable[ReadinessCheck],
) -> bool:
    """
    Evaluate a collection of readiness checks.

    Exceptions from individual checks are treated as failures.
    """
    for check in checks:
        try:
            if not bool(check()):
                return False
        except Exception:
            return False

    return True


__all__ = [
    "ReadinessCheck",
    "ReadinessChecker",
    "ReadinessResult",
    "ReadinessStatus",
    "all_ready",
]