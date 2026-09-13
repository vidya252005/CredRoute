"""Configurable offer scoring. Default weights match the existing ranker."""

from __future__ import annotations

from typing import Any

from app.domain.context import DecisionContext
from app.domain.results import LenderOffer
from app.services.underwriting_rules import load_underwriting_rules


def _weights() -> dict[str, float]:
    routing = load_underwriting_rules().get("routing") or {}
    return routing.get("weights") or {
        "approvalProbability": 0.3,
        "interestScore": 0.2,
        "amountMatch": 0.15,
        "profileFit": 0.2,
        "lenderSuccessRate": 0.1,
        "journeyScore": 0.05,
    }


class OfferScorer:
    def score(self, offer: LenderOffer, context: DecisionContext, lowest_rate: float | None = None) -> float:
        weights = _weights()
        rate = offer.interest_rate or lowest_rate or 1
        interest_score = (lowest_rate / rate) if lowest_rate and rate else 0
        amount = context.application.requested_amount
        max_amount = offer.max_amount or amount
        amount_match = min(1, amount / max_amount) if max_amount else 0
        return round(
            weights.get("approvalProbability", 0.3) * offer.approval_probability
            + weights.get("interestScore", 0.2) * interest_score
            + weights.get("amountMatch", 0.15) * amount_match
            + weights.get("profileFit", 0.2) * offer.profile_fit
            + weights.get("lenderSuccessRate", 0.1) * offer.success_rate
            + weights.get("journeyScore", 0.05) * offer.journey_score,
            3,
        )

    def score_dict(self, offer: dict[str, Any], input_data: dict[str, Any], lowest_rate: float) -> float:
        context = DecisionContext.from_input(input_data)
        return self.score(LenderOffer.from_dict(offer), context, lowest_rate)
