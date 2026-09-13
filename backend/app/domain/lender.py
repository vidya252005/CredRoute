"""Lender catalog, policy, and adapter request/response types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.lender_policy import normalize_lender_policy


@dataclass(slots=True)
class LenderPolicy:
    min_credit_score: int | None
    max_foir: float
    min_income: int | None
    max_amount: int | None
    min_amount: int | None
    accepted_income_types: set[str]
    accepted_city_tiers: set[int]
    serves_thin_file: bool
    serves_prime: bool = False
    serves_near_prime: bool = False
    base_interest_rate: float = 14.0
    processing_fee: int = 0
    success_rate: float = 0.8
    journey_score: float = 0.8

    @classmethod
    def from_lender_dict(cls, lender: dict[str, Any]) -> LenderPolicy:
        policy = normalize_lender_policy(lender)
        income_types = policy.get("income_types") or []
        city_tiers = policy.get("city_tiers") or []
        return cls(
            min_credit_score=policy.get("min_credit_score"),
            max_foir=float(policy.get("max_foir") or 0.6),
            min_income=policy.get("min_income"),
            max_amount=policy.get("max_amount"),
            min_amount=lender.get("min_amount", lender.get("minAmount")),
            accepted_income_types=set(income_types),
            accepted_city_tiers=set(city_tiers),
            serves_thin_file=bool(policy.get("serves_thin_file")),
            serves_prime=bool(policy.get("serves_prime")),
            serves_near_prime=bool(policy.get("serves_near_prime")),
            base_interest_rate=float(policy.get("base_interest_rate") or 14),
            processing_fee=int(lender.get("processing_fee", lender.get("processingFee", 0)) or 0),
            success_rate=float(lender.get("success_rate", lender.get("successRate", 0.8)) or 0.8),
            journey_score=float(lender.get("journey_score", lender.get("journeyScore", 0.8)) or 0.8),
        )


@dataclass(slots=True)
class LenderRecord:
    id: int
    code: str
    name: str
    active: bool
    category: str
    policy: LenderPolicy
    raw: dict[str, Any] = field(default_factory=dict)

    def supports_amount(self, amount: int) -> bool:
        if self.policy.max_amount is None:
            return True
        return amount <= self.policy.max_amount

    def supports_product(self, _product_type: str) -> bool:
        return True


@dataclass(slots=True)
class LenderEligibilityRequest:
    lender: LenderRecord
    input_data: dict[str, Any]
    profile: dict[str, Any]


@dataclass(slots=True)
class LenderEligibilityResponse:
    eligible: bool
    reason: str | None = None
    fit: float = 0.0
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OfferRequest:
    lender: LenderRecord
    input_data: dict[str, Any]
    risk: dict[str, Any]
    profile: dict[str, Any]
    fit: float


@dataclass(slots=True)
class ProviderHealth:
    lender_code: str
    healthy: bool
    circuit_state: str
    detail: str | None = None
