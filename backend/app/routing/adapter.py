"""Lender adapter boundary — lender-specific APIs never leak into scoring."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.lender import (
    LenderEligibilityRequest,
    LenderEligibilityResponse,
    OfferRequest,
    ProviderHealth,
)
from app.domain.results import LenderOffer
from app.lenders.base import MockLenderProvider
from app.resilience.circuit_breaker import get_circuit_state


class LenderAdapter(ABC):
    code: str

    @abstractmethod
    async def check_eligibility(self, request: LenderEligibilityRequest) -> LenderEligibilityResponse:
        raise NotImplementedError

    @abstractmethod
    async def get_offer(self, request: OfferRequest) -> LenderOffer:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        raise NotImplementedError


class MockLenderAdapter(LenderAdapter):
    def __init__(self, code: str, provider: MockLenderProvider | None = None):
        self.code = code
        self.provider = provider or MockLenderProvider(code)

    async def check_eligibility(self, request: LenderEligibilityRequest) -> LenderEligibilityResponse:
        raw = await self.provider.check_eligibility(
            request.lender.raw, request.input_data, request.profile
        )
        return LenderEligibilityResponse(
            eligible=bool(raw.get("eligible")),
            reason=raw.get("reason"),
            fit=float(raw.get("fit") or 0),
            rejection_reasons=[raw["reason"]] if raw.get("reason") and not raw.get("eligible") else [],
        )

    async def get_offer(self, request: OfferRequest) -> LenderOffer:
        raw = await self.provider.fetch_offer(
            request.lender.raw,
            request.input_data,
            request.risk,
            request.profile,
            request.fit,
        )
        return LenderOffer.from_dict(raw)

    async def health_check(self) -> ProviderHealth:
        state = get_circuit_state(self.code)
        return ProviderHealth(
            lender_code=self.code,
            healthy=state.state != "open",
            circuit_state=state.state,
        )


class RawLenderResponse(dict):
    """Normalized envelope for a lender-specific payload before OfferNormalizer."""
