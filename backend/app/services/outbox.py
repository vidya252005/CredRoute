"""Transactional outbox — enqueue in the same commit as the decision."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.entities import OutboxEvent
from app.services.events import (
    EVENT_APPLICATION_CREATED,
    EVENT_DECISION_GENERATED,
    EVENT_RISK_COMPLETED,
    publish_event,
)


def queue_decision_events(db: Session, application_id: int, decision: dict, risk: dict) -> None:
    events = [
        (EVENT_APPLICATION_CREATED, {"applicationId": application_id}),
        (
            EVENT_RISK_COMPLETED,
            {
                "applicationId": application_id,
                "defaultProbability": risk.get("defaultProbability"),
                "fraudProbability": risk.get("fraudProbability"),
            },
        ),
        (
            EVENT_DECISION_GENERATED,
            {
                "applicationId": application_id,
                "decision": decision.get("decision"),
                "status": decision.get("status"),
            },
        ),
    ]
    for event_type, payload in events:
        db.add(OutboxEvent(event_type=event_type, payload=payload))


def publish_pending_outbox(db: Session, limit: int = 50) -> int:
    rows = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.id)
        .limit(limit)
        .all()
    )
    published = 0
    now = datetime.now(UTC)
    for row in rows:
        if publish_event(row.event_type, row.payload) is not None:
            row.published_at = now
            published += 1
    if published:
        db.commit()
    return published
