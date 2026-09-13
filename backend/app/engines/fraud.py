"""Fraud engine — velocity, stacking, and device-integrity signals."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.context import DecisionContext
from app.domain.enums import FraudRiskLevel
from app.domain.results import FraudFlag, FraudResult
from app.services.fraud import evaluate_fraud


class FraudEngine:
    def evaluate(self, context: DecisionContext, db: Session | None) -> FraudResult:
        risk = context.risk_result.to_dict() if context.risk_result else {}
        raw = evaluate_fraud(db, context.to_input_data(), risk)
        probability = float(raw.get("fraudProbability") or 0)
        if raw.get("blocked") or probability >= 0.25:
            level = FraudRiskLevel.HIGH
        elif probability >= 0.15:
            level = FraudRiskLevel.MEDIUM
        else:
            level = FraudRiskLevel.LOW
        flags = [FraudFlag(code="SIGNAL", message=str(item)) for item in raw.get("signals") or []]
        return FraudResult(
            fraud_probability=probability,
            risk_level=level,
            flags=flags,
            blocked=bool(raw.get("blocked")),
            raw=raw,
        )
