"""Decision policy — APPROVE / REJECT / REFER, not which lender to use."""

from __future__ import annotations

from app.domain.context import DecisionContext
from app.domain.enums import DecisionOutcome, FraudRiskLevel
from app.domain.results import DecisionResult
from app.services.decision_engine import evaluate_decision


class DecisionPolicy:
    def decide(self, context: DecisionContext) -> DecisionResult:
        eligibility = context.eligibility_result.to_dict() if context.eligibility_result else {"eligible": False}
        risk = context.risk_result.to_dict() if context.risk_result else {}
        fraud = context.fraud_result.to_dict() if context.fraud_result else {}
        alt_data = context.alt_data_result.to_dict() if context.alt_data_result else {}
        raw = evaluate_decision(eligibility, risk, fraud, alt_data)
        return DecisionResult(
            outcome=DecisionOutcome(raw.get("decision") or "reject"),
            status=str(raw.get("status") or "ineligible"),
            reasons=list(raw.get("reasons") or []),
            explainability=raw.get("explainability") or {},
            raw=raw,
        )

    def hard_gates(self, context: DecisionContext) -> DecisionResult | None:
        """Optional explicit gates used by tests and explainability — policy still delegates to rules."""
        fraud = context.fraud_result
        if fraud and fraud.risk_level == FraudRiskLevel.HIGH and fraud.blocked:
            return DecisionResult(
                outcome=DecisionOutcome.reject,
                status="rejected",
                reasons=["FRAUD_RISK"],
                raw={"decision": "reject", "status": "rejected", "reasons": ["FRAUD_RISK"]},
            )
        return None
