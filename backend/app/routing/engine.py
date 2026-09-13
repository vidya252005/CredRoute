"""Routing engine — candidate filter, concurrent query, score, select."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.context import DecisionContext
from app.domain.lender import LenderPolicy, LenderRecord
from app.domain.results import LenderOffer, RoutingResult
from app.models.entities import Lender
from app.routing.candidate import CandidateSelector
from app.services.lender_policies import lender_to_routing_dict
from app.routing.coordinator import LenderQueryCoordinator
from app.routing.eligibility import LenderEligibilityEngine
from app.routing.strategies import RoutingStrategy, resolve_strategy


def lender_row_to_dict(lender: Lender) -> dict:
    policy = lender.policy or {}
    return {"id": lender.id, "code": lender.code, "name": lender.name, "category": lender.category, **policy}


class RoutingEngine:
    def __init__(
        self,
        strategy: RoutingStrategy | None = None,
        coordinator: LenderQueryCoordinator | None = None,
        candidate_selector: CandidateSelector | None = None,
        eligibility_engine: LenderEligibilityEngine | None = None,
    ):
        self.strategy = strategy or resolve_strategy(settings.routing_strategy)
        self.coordinator = coordinator or LenderQueryCoordinator()
        self.candidate_selector = candidate_selector or CandidateSelector()
        self.eligibility_engine = eligibility_engine or LenderEligibilityEngine()

    def load_lenders(self, db: Session) -> list[LenderRecord]:
        rows = db.query(Lender).filter(Lender.active.is_(True)).all()
        records = []
        for row in rows:
            raw = lender_to_routing_dict(db, row)
            records.append(
                LenderRecord(
                    id=row.id,
                    code=row.code,
                    name=row.name,
                    active=bool(row.active),
                    category=row.category,
                    policy=LenderPolicy.from_lender_dict(raw),
                    raw=raw,
                )
            )
        return records

    async def route(self, db: Session, context: DecisionContext, scored: dict) -> RoutingResult:
        profile = scored["eligibility"]["profile"]
        risk = scored["risk"]
        priced_input = scored["pricedInput"]
        routing_ctx = context.routing_context(priced_input, profile, risk)
        priced_context = routing_ctx.to_decision_context()

        lenders = self.load_lenders(db)
        candidates = self.candidate_selector.select(lenders, priced_context)
        evaluations = await self.coordinator.query_all(candidates, priced_context, risk, profile)

        raw_offers = [
            evaluation.offer.to_dict()
            for evaluation in evaluations
            if evaluation.offer is not None
        ]
        ranked = self.strategy.rank(raw_offers, priced_input, profile)
        for offer in ranked:
            offer["maxAmount"] = min(offer.get("maxAmount", priced_input["amount"]), priced_input["amount"])

        if not ranked and scored["altData"].get("thinFileEligible"):
            ranked = self._thin_file_fallback(lenders, scored)

        offers = [LenderOffer.from_dict(item) for item in ranked]
        selected = self.strategy.select(offers)
        attempts = [
            {k: v for k, v in evaluation.to_attempt_dict().items() if k != "offer"}
            for evaluation in evaluations
        ]
        explanations = [
            evaluation.explanation for evaluation in evaluations if evaluation.explanation is not None
        ]
        for offer in offers:
            for explanation in explanations:
                if explanation.lender_code == offer.lender_code:
                    explanation.score = offer.score
                    explanation.eligible = True

        result = RoutingResult(
            application_id=context.application.id,
            selected_offer=selected,
            selected_lender=selected.lender_code if selected else None,
            candidates=evaluations,
            offers=offers,
            routing_strategy=self.strategy.name,
            routing_version=settings.routing_policy_version,
            explanation=explanations,
            attempts=attempts,
        )
        context.routing_result = result
        return result

    def _thin_file_fallback(self, lenders: list[LenderRecord], scored: dict) -> list[dict]:
        originator = next((item for item in lenders if item.policy.serves_thin_file), None)
        if not originator:
            return []
        priced = scored["personalizedOffer"]
        alt_score = float(scored.get("altData", {}).get("altDataScore") or 0.55)
        approval = round(min(0.85, max(0.40, 0.45 + alt_score * 0.4)), 3)
        fit = round(min(0.95, max(0.45, 0.50 + alt_score * 0.4)), 3)
        return [
            {
                "lenderId": originator.id,
                "lenderCode": originator.code,
                "lenderName": originator.name,
                "interestRate": priced["apr"],
                "processingFee": originator.policy.processing_fee,
                "approvalProbability": approval,
                "maxAmount": priced["offeredAmount"],
                "successRate": originator.policy.success_rate,
                "journeyScore": originator.policy.journey_score,
                "profileFit": fit,
                "rank": 1,
                "score": fit,
                "monthlyPayment": priced["monthlyPayment"],
                "simulatedOffer": True,
                "routingReason": (
                    "Simulated starter-ticket fallback after bureau-path lenders declined; "
                    "not a calibrated approval probability"
                ),
            }
        ]
