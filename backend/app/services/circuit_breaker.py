import time
from dataclasses import dataclass, field


@dataclass
class CircuitState:
    failures: int = 0
    successes: int = 0
    open_until: float = 0
    state: str = "closed"


_states: dict[str, CircuitState] = {}


def get_circuit_state(lender_code: str) -> CircuitState:
    return _states.get(lender_code, CircuitState())


def record_success(lender_code: str) -> None:
    _states[lender_code] = CircuitState(successes=get_circuit_state(lender_code).successes + 1)


def record_failure(lender_code: str, failure_threshold: int = 3, cooldown_ms: int = 30000) -> CircuitState:
    current = get_circuit_state(lender_code)
    current.failures += 1
    current.successes = 0
    if current.failures >= failure_threshold:
        current.state = "open"
        current.open_until = time.time() + cooldown_ms / 1000
    _states[lender_code] = current
    return current


def is_circuit_open(lender_code: str) -> bool:
    current = get_circuit_state(lender_code)
    if current.state != "open":
        return False
    if time.time() >= current.open_until:
        current.state = "half_open"
        _states[lender_code] = current
        return False
    return True


def circuit_snapshot() -> list[dict]:
    return [
        {
            "lenderCode": code,
            "failures": state.failures,
            "successes": state.successes,
            "openUntil": state.open_until,
            "state": state.state,
        }
        for code, state in _states.items()
    ]
