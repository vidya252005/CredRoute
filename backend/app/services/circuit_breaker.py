import json
import time
from dataclasses import asdict, dataclass

import redis

from app.core.cache import get_redis

_PREFIX = "credroute:cb:"
_TTL_SECONDS = 3600


@dataclass
class CircuitState:
    failures: int = 0
    successes: int = 0
    open_until: float = 0
    state: str = "closed"


_states: dict[str, CircuitState] = {}


def _key(lender_code: str) -> str:
    return f"{_PREFIX}{lender_code}"


def _from_payload(payload: dict) -> CircuitState:
    return CircuitState(
        failures=int(payload.get("failures") or 0),
        successes=int(payload.get("successes") or 0),
        open_until=float(payload.get("open_until") or 0),
        state=str(payload.get("state") or "closed"),
    )


def _persist(lender_code: str, state: CircuitState) -> None:
    _states[lender_code] = state
    client = get_redis()
    if not client:
        return
    try:
        client.setex(_key(lender_code), _TTL_SECONDS, json.dumps(asdict(state)))
    except redis.RedisError:
        return


def get_circuit_state(lender_code: str) -> CircuitState:
    client = get_redis()
    if client:
        try:
            raw = client.get(_key(lender_code))
            if raw:
                state = _from_payload(json.loads(raw))
                _states[lender_code] = state
                return state
        except (redis.RedisError, json.JSONDecodeError, TypeError):
            pass
    return _states.get(lender_code, CircuitState())


def record_success(lender_code: str) -> None:
    current = get_circuit_state(lender_code)
    _persist(lender_code, CircuitState(successes=current.successes + 1))


def record_failure(lender_code: str, failure_threshold: int = 3, cooldown_ms: int = 30000) -> CircuitState:
    current = get_circuit_state(lender_code)
    current.failures += 1
    current.successes = 0
    if current.failures >= failure_threshold:
        current.state = "open"
        current.open_until = time.time() + cooldown_ms / 1000
    _persist(lender_code, current)
    return current


def is_circuit_open(lender_code: str) -> bool:
    current = get_circuit_state(lender_code)
    if current.state != "open":
        return False
    if time.time() >= current.open_until:
        current.state = "half_open"
        _persist(lender_code, current)
        return False
    return True


def circuit_snapshot() -> list[dict]:
    codes = set(_states)
    client = get_redis()
    if client:
        try:
            for key in client.scan_iter(match=f"{_PREFIX}*"):
                codes.add(str(key).removeprefix(_PREFIX))
        except redis.RedisError:
            pass
    return [
        {
            "lenderCode": code,
            "failures": state.failures,
            "successes": state.successes,
            "openUntil": state.open_until,
            "state": state.state,
        }
        for code in sorted(codes)
        for state in [get_circuit_state(code)]
    ]
