"""Redis Streams event bus (Kafka-shaped events without extra infra)."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from app.core.cache import get_redis

STREAM = "credroute.events"
EVENT_APPLICATION_CREATED = "LoanApplicationCreated"
EVENT_RISK_COMPLETED = "RiskEvaluationCompleted"
EVENT_DECISION_GENERATED = "LoanDecisionGenerated"


def publish_event(event_type: str, payload: dict) -> str | None:
    client = get_redis()
    if not client:
        return None
    body = {
        "eventType": event_type,
        "occurredAt": datetime.now(UTC).isoformat(),
        "payload": json.dumps(payload),
    }
    try:
        return client.xadd(STREAM, body, maxlen=10000, approximate=True)
    except Exception:
        return None


def consume_events(count: int = 100, block_ms: int = 10) -> list[dict]:
    client = get_redis()
    if not client:
        return []
    try:
        rows = client.xread({STREAM: "0-0"}, count=count, block=block_ms)
    except Exception:
        return []
    events = []
    for _stream, messages in rows or []:
        for message_id, fields in messages:
            events.append(
                {
                    "id": message_id,
                    "eventType": fields.get("eventType"),
                    "occurredAt": fields.get("occurredAt"),
                    "payload": json.loads(fields.get("payload") or "{}"),
                }
            )
    return events


def publish_decision_pipeline(application_id: int, decision: dict, risk: dict) -> None:
    started = time.perf_counter()
    publish_event(EVENT_APPLICATION_CREATED, {"applicationId": application_id})
    publish_event(
        EVENT_RISK_COMPLETED,
        {
            "applicationId": application_id,
            "defaultProbability": risk.get("defaultProbability"),
            "fraudProbability": risk.get("fraudProbability"),
        },
    )
    publish_event(
        EVENT_DECISION_GENERATED,
        {
            "applicationId": application_id,
            "decision": decision.get("decision"),
            "status": decision.get("status"),
            "publishLatencyMs": round((time.perf_counter() - started) * 1000, 3),
        },
    )
