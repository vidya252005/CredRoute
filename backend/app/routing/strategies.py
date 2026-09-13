"""Ranking strategies for selecting among eligible lender offers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.results import LenderOffer
from app.services.offer_ranking import rank_offers


class RoutingStrategy(ABC):
    name = "balanced"

    @abstractmethod
    def select(self, offers: list[LenderOffer]) -> LenderOffer | None:
        raise NotImplementedError

    def rank(self, raw_offers: list[dict], input_data: dict, profile: dict) -> list[dict]:
        return rank_offers(raw_offers, input_data, profile)


class BalancedStrategy(RoutingStrategy):
    name = "balanced"

    def select(self, offers: list[LenderOffer]) -> LenderOffer | None:
        if not offers:
            return None
        return max(offers, key=lambda item: item.score)


class BestApprovalStrategy(RoutingStrategy):
    name = "best_approval"

    def select(self, offers: list[LenderOffer]) -> LenderOffer | None:
        if not offers:
            return None
        return max(offers, key=lambda item: item.approval_probability)

    def rank(self, raw_offers: list[dict], input_data: dict, profile: dict) -> list[dict]:
        ranked = rank_offers(raw_offers, input_data, profile)
        ranked.sort(key=lambda item: item.get("approvalProbability", 0), reverse=True)
        for index, offer in enumerate(ranked, start=1):
            offer["rank"] = index
        return ranked


class LowestCostStrategy(RoutingStrategy):
    name = "lowest_cost"

    def select(self, offers: list[LenderOffer]) -> LenderOffer | None:
        if not offers:
            return None
        return min(offers, key=lambda item: (item.interest_rate, item.processing_fee))

    def rank(self, raw_offers: list[dict], input_data: dict, profile: dict) -> list[dict]:
        ranked = rank_offers(raw_offers, input_data, profile)
        ranked.sort(key=lambda item: (item.get("interestRate", 99), item.get("processingFee", 0)))
        for index, offer in enumerate(ranked, start=1):
            offer["rank"] = index
        return ranked


class CustomerPreferredStrategy(RoutingStrategy):
    name = "customer_preferred"

    def select(self, offers: list[LenderOffer]) -> LenderOffer | None:
        if not offers:
            return None
        return max(offers, key=lambda item: (item.journey_score, item.profile_fit, item.score))


def resolve_strategy(name: str | None) -> RoutingStrategy:
    mapping = {
        BalancedStrategy.name: BalancedStrategy,
        BestApprovalStrategy.name: BestApprovalStrategy,
        LowestCostStrategy.name: LowestCostStrategy,
        CustomerPreferredStrategy.name: CustomerPreferredStrategy,
    }
    return mapping.get(name or BalancedStrategy.name, BalancedStrategy)()
