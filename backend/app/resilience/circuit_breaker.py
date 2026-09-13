"""Class-based circuit breaker; module-level registry stays API-compatible."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.enums import CircuitStateName
from app.services.circuit_breaker import (
    CircuitState,
    circuit_snapshot,
    get_circuit_state,
    is_circuit_open,
    record_failure,
    record_success,
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitStateName",
    "circuit_snapshot",
    "get_circuit_state",
    "is_circuit_open",
    "record_failure",
    "record_success",
]


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_ms: int = 30000,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(milliseconds=recovery_timeout_ms)

    def allow_request(self) -> bool:
        return not is_circuit_open(self.name)

    def record_success(self) -> None:
        record_success(self.name)

    def record_failure(self) -> CircuitState:
        return record_failure(self.name, self.failure_threshold, int(self.recovery_timeout.total_seconds() * 1000))

    @property
    def state(self) -> CircuitState:
        return get_circuit_state(self.name)

    @property
    def opened_at(self) -> datetime | None:
        current = self.state
        if current.state != CircuitStateName.OPEN.value or not current.open_until:
            return None
        return datetime.fromtimestamp(current.open_until) - self.recovery_timeout
