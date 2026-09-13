"""Decision engine — risk, fraud, alt-data, affordability, then policy."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.domain.context import DecisionContext
from app.domain.results import EligibilityResult
from app.engines.affordability import AffordabilityEngine
from app.engines.alternative_data import AlternativeDataEngine
from app.engines.consent import ConsentService
from app.engines.fraud import FraudEngine
from app.engines.policy import DecisionPolicy
from app.engines.risk import CachedRiskEngine, RiskEngine
from app.services.compliance import adverse_action
from app.services.credit_line import (
    get_or_create_credit_line,
    serialize_line,
    starter_limit,
    stepped_limit,
)
from app.services.eligibility import evaluate_eligibility
from app.services.model_monitoring import evaluate_drift
from app.services.offer_pricing import price_offer
from app.models.entities import BorrowerCreditLine


class DecisionEngine:
    def __init__(
        self,
        risk_engine: RiskEngine | None = None,
        fraud_engine: FraudEngine | None = None,
        alternative_data_engine: AlternativeDataEngine | None = None,
        affordability_engine: AffordabilityEngine | None = None,
        policy_engine: DecisionPolicy | None = None,
        consent_service: ConsentService | None = None,
    ):
        self.risk_engine = risk_engine or CachedRiskEngine()
        self.fraud_engine = fraud_engine or FraudEngine()
        self.alternative_data_engine = alternative_data_engine or AlternativeDataEngine()
        self.affordability_engine = affordability_engine or AffordabilityEngine()
        self.policy_engine = policy_engine or DecisionPolicy()
        self.consent_service = consent_service or ConsentService()

    def evaluate(
        self,
        context: DecisionContext,
        db: Session | None,
        persist_credit_line: bool = True,
    ) -> dict:
        started = time.perf_counter()
        input_data = context.to_input_data()

        context.risk_result = self.risk_engine.score(context)
        context.affordability = self.affordability_engine.calculate(context)

        existing_line = None
        if db is not None:
            from app.core.identity import SensitiveIdentity

            existing_line = (
                db.query(BorrowerCreditLine)
                .filter(BorrowerCreditLine.pan_hash == SensitiveIdentity(input_data["pan"]).pan_hash)
                .first()
            )
        credit_preview = (
            serialize_line(existing_line)
            if existing_line
            else {
                "firstLoan": True,
                "onTimeRepayments": 0,
                "currentLimit": 0,
                "nextLimit": 0,
                "originatedCount": 0,
            }
        )
        context.credit_line = credit_preview
        context.alt_data_result = self.alternative_data_engine.evaluate(context)
        alt_data = context.alt_data_result.to_dict()

        if persist_credit_line and db is not None:
            line = get_or_create_credit_line(
                db, input_data["pan"], input_data["monthly_income"], alt_data["altDataScore"]
            )
            if line.originated_count == 0:
                line.current_limit = starter_limit(input_data["monthly_income"], alt_data["altDataScore"])
                line.starter_limit = line.current_limit
                line.next_limit = stepped_limit(line.starter_limit, 1, input_data["monthly_income"])
            credit = serialize_line(line)
        elif existing_line:
            credit = serialize_line(existing_line)
        else:
            base = starter_limit(input_data["monthly_income"], alt_data["altDataScore"])
            credit = {
                "firstLoan": True,
                "currentLimit": base,
                "nextLimit": stepped_limit(base, 1, input_data["monthly_income"]),
                "onTimeRepayments": 0,
                "originatedCount": 0,
            }
        context.credit_line = credit

        profile = (context.risk_result.engineered_features or {}).get("profile") or {}
        segment = profile.get("segment") or context.risk_result.segment or "near_prime"
        priced = price_offer(input_data, context.risk_result.to_dict(), alt_data, credit, segment)
        priced_input = context.with_priced_amount(priced["offeredAmount"], priced["tenureMonths"])
        context.personalized_offer = priced
        context.input_data = {**input_data, **priced_input}

        eligibility_raw = evaluate_eligibility(
            input_data,
            offered_amount=priced["offeredAmount"],
            offered_tenure=priced["tenureMonths"],
        )
        context.eligibility_result = EligibilityResult(
            eligible=bool(eligibility_raw.get("eligible")),
            reason=eligibility_raw.get("reason"),
            checks=list(eligibility_raw.get("checks") or []),
            profile=eligibility_raw.get("profile") or {},
            foir=eligibility_raw.get("foir") or {},
            rules_version=eligibility_raw.get("rulesVersion"),
            raw=eligibility_raw,
        )

        priced_context = context.with_priced_ticket(priced_input)
        context.fraud_result = self.fraud_engine.evaluate(priced_context, db)

        risk = {
            **context.risk_result.to_dict(),
            "fraud": context.fraud_result.to_dict(),
            "fraudProbability": context.fraud_result.fraud_probability,
            "drift": evaluate_drift(input_data),
            "altData": alt_data,
            "creditLine": credit,
            "personalizedOffer": priced,
        }
        context.risk_result.raw = risk

        context.decision_result = self.policy_engine.decide(context)
        consent = self.consent_service.record(input_data, alt_data, bool(input_data.get("consent_alt_data")))
        action = adverse_action(
            context.decision_result.to_dict(),
            eligibility_raw,
            alt_data,
            context.fraud_result.to_dict(),
        )
        scored_ms = round((time.perf_counter() - started) * 1000)
        priced["scoredInMs"] = scored_ms
        decision = context.decision_result.to_dict()
        decision["adverseAction"] = action
        context.decision_result.raw = decision
        context.consent = consent
        context.adverse_action = action
        context.scored_in_ms = scored_ms
        context.personalized_offer = priced
        risk.update(
            {
                "decision": decision,
                "consent": consent,
                "adverseAction": action,
                "scoredInMs": scored_ms,
                "personalizedOffer": priced,
            }
        )
        context.risk_result.raw = risk
        return {
            "eligibility": eligibility_raw,
            "risk": risk,
            "fraud": context.fraud_result.to_dict(),
            "decision": decision,
            "altData": alt_data,
            "creditLine": credit,
            "personalizedOffer": priced,
            "consent": consent,
            "adverseAction": action,
            "pricedInput": priced_input,
            "context": context,
        }
