"""Typed results produced by decisioning and routing engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.enums import DecisionOutcome, FraudRiskLevel, LenderAttemptStatus


@dataclass(slots=True)
class RiskResult:
    default_probability: float
    risk_band: str
    segment: str | None = None
    confidence: float = 0.0
    model_source: str | None = None
    model_version: str | None = None
    risk_factors: list[str] = field(default_factory=list)
    shap_factors: list[Any] = field(default_factory=list)
    engineered_features: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass(slots=True)
class FraudFlag:
    code: str
    message: str


@dataclass(slots=True)
class FraudResult:
    fraud_probability: float
    risk_level: FraudRiskLevel
    flags: list[FraudFlag] = field(default_factory=list)
    blocked: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass(slots=True)
class AlternativeDataResult:
    usable: bool
    signals: dict[str, Any]
    confidence: float
    thin_file_eligible: bool = False
    reasons: list[str] = field(default_factory=list)
    consent_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass(slots=True)
class EligibilityResult:
    eligible: bool
    reason: str | None = None
    checks: list[dict[str, Any]] = field(default_factory=list)
    profile: dict[str, Any] = field(default_factory=dict)
    foir: dict[str, Any] = field(default_factory=dict)
    rules_version: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass(slots=True)
class DecisionResult:
    outcome: DecisionOutcome
    status: str
    reasons: list[str] = field(default_factory=list)
    explainability: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass(slots=True)
class LenderDecisionExplanation:
    lender_code: str
    eligible: bool
    rejection_reasons: list[str] = field(default_factory=list)
    policy_version: str | None = None
    risk_contribution: float = 0.0
    profile_fit: float = 0.0
    score: float | None = None
    latency_ms: int | None = None
    status: str | None = None


@dataclass(slots=True)
class LenderOffer:
    lender_id: int
    lender_code: str
    lender_name: str
    interest_rate: float
    processing_fee: int
    approval_probability: float
    max_amount: int
    success_rate: float = 0.0
    journey_score: float = 0.0
    profile_fit: float = 0.0
    score: float = 0.0
    rank: int = 0
    monthly_payment: int = 0
    routing_reason: str | None = None
    latency_ms: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.raw)
        payload.update(
            {
                "lenderId": self.lender_id,
                "lenderCode": self.lender_code,
                "lenderName": self.lender_name,
                "interestRate": self.interest_rate,
                "processingFee": self.processing_fee,
                "approvalProbability": self.approval_probability,
                "maxAmount": self.max_amount,
                "successRate": self.success_rate,
                "journeyScore": self.journey_score,
                "profileFit": self.profile_fit,
                "score": self.score,
                "rank": self.rank,
                "monthlyPayment": self.monthly_payment,
                "routingReason": self.routing_reason,
            }
        )
        if self.latency_ms is not None:
            payload["latencyMs"] = self.latency_ms
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LenderOffer:
        return cls(
            lender_id=int(payload.get("lenderId") or 0),
            lender_code=str(payload.get("lenderCode") or ""),
            lender_name=str(payload.get("lenderName") or ""),
            interest_rate=float(payload.get("interestRate") or 0),
            processing_fee=int(payload.get("processingFee") or 0),
            approval_probability=float(payload.get("approvalProbability") or 0),
            max_amount=int(payload.get("maxAmount") or 0),
            success_rate=float(payload.get("successRate") or 0),
            journey_score=float(payload.get("journeyScore") or 0),
            profile_fit=float(payload.get("profileFit") or 0),
            score=float(payload.get("score") or 0),
            rank=int(payload.get("rank") or 0),
            monthly_payment=int(payload.get("monthlyPayment") or 0),
            routing_reason=payload.get("routingReason"),
            latency_ms=payload.get("latencyMs"),
            raw=dict(payload),
        )


@dataclass(slots=True)
class LenderEvaluation:
    lender_code: str
    status: LenderAttemptStatus
    latency_ms: int = 0
    message: str | None = None
    offer: LenderOffer | None = None
    circuit: dict[str, Any] | None = None
    explanation: LenderDecisionExplanation | None = None

    def to_attempt_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status.value,
            "lenderCode": self.lender_code,
            "latencyMs": self.latency_ms,
        }
        if self.message:
            payload["message"] = self.message
        if self.circuit:
            payload["circuit"] = self.circuit
        if self.offer is not None:
            payload["offer"] = self.offer.to_dict()
        return payload


@dataclass(slots=True)
class RoutingResult:
    application_id: int | None
    selected_offer: LenderOffer | None
    selected_lender: str | None
    candidates: list[LenderEvaluation] = field(default_factory=list)
    offers: list[LenderOffer] = field(default_factory=list)
    routing_strategy: str = "balanced"
    routing_version: str = "1.0.0"
    explanation: list[LenderDecisionExplanation] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
