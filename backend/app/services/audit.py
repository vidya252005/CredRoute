"""Persist decision snapshots so historical decisions are never recomputed."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.context import DecisionContext
from app.domain.results import RoutingResult
from app.models.entities import (
    DecisionAudit,
    FraudAssessment,
    LenderAttemptRecord,
    RiskAssessment,
    RoutingCandidate,
    RoutingDecision,
)
from app.services.underwriting_rules import load_underwriting_rules


def persist_decision_audit(
    db: Session,
    application_id: int,
    context: DecisionContext,
    scored: dict[str, Any],
    routing: RoutingResult | None,
) -> DecisionAudit:
    rules = load_underwriting_rules()
    risk = context.risk_result
    fraud = context.fraud_result
    decision = scored.get("decision") or {}

    if risk:
        db.add(
            RiskAssessment(
                application_id=application_id,
                default_probability=risk.default_probability,
                risk_band=risk.risk_band,
                model_name=risk.model_source,
                model_version=risk.model_version,
            )
        )
    if fraud:
        db.add(
            FraudAssessment(
                application_id=application_id,
                fraud_probability=fraud.fraud_probability,
                risk_level=fraud.risk_level.value,
                flags=fraud.to_dict(),
                model_version="fraud-rules-1",
            )
        )

    audit = DecisionAudit(
        application_id=application_id,
        model_version=(risk.model_source if risk else None) or "unknown",
        policy_version=str(rules.get("version") or "1.0.0"),
        routing_version=routing.routing_version if routing else None,
        feature_snapshot=(risk.engineered_features if risk else None) or {},
        lender_results=routing.attempts if routing else [],
        final_decision=str(decision.get("decision") or "reject"),
        reasons=list(decision.get("reasons") or []),
        explainability=decision.get("explainability") or {},
    )
    db.add(audit)
    db.flush()

    if routing:
        selected_offer_id = None
        routing_row = RoutingDecision(
            application_id=application_id,
            selected_offer_id=selected_offer_id,
            selected_lender=routing.selected_lender,
            strategy=routing.routing_strategy,
            strategy_version=routing.routing_version,
            policy_version=str(rules.get("version") or "1.0.0"),
        )
        db.add(routing_row)
        db.flush()
        for evaluation in routing.candidates:
            db.add(
                RoutingCandidate(
                    decision_id=routing_row.id,
                    lender_code=evaluation.lender_code,
                    eligible=evaluation.offer is not None,
                    score=evaluation.offer.score if evaluation.offer else None,
                    rejection_reasons=evaluation.explanation.rejection_reasons if evaluation.explanation else [],
                    latency_ms=evaluation.latency_ms,
                    status=evaluation.status.value,
                )
            )
            db.add(
                LenderAttemptRecord(
                    application_id=application_id,
                    lender_code=evaluation.lender_code,
                    attempt_number=1,
                    status=evaluation.status.value,
                    latency_ms=evaluation.latency_ms,
                    error_code=None if evaluation.offer else evaluation.status.value,
                    error_message=evaluation.message,
                )
            )
    return audit
