"""Consent verification — kept out of API handlers and scoring."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import AppError
from app.domain.enums import ConsentPurpose, ConsentStatus
from app.services.compliance import build_consent


@dataclass(slots=True)
class ConsentDecision:
    status: ConsentStatus
    purpose: ConsentPurpose | None = None
    message: str | None = None


class ConsentService:
    ALT_DATA_MESSAGE = (
        "Consent is required to use cash-flow and device-proxy signals for underwriting."
    )

    def verify(self, granted: bool, purpose: ConsentPurpose = ConsentPurpose.cashflow) -> ConsentDecision:
        if not granted:
            return ConsentDecision(
                status=ConsentStatus.CONSENT_REQUIRED,
                purpose=purpose,
                message=self.ALT_DATA_MESSAGE,
            )
        return ConsentDecision(status=ConsentStatus.CONSENT_VALID, purpose=purpose)

    def require_alt_data(self, granted: bool) -> ConsentDecision:
        decision = self.verify(granted, ConsentPurpose.cashflow)
        if decision.status == ConsentStatus.CONSENT_REQUIRED:
            raise AppError("CONSENT_REQUIRED", self.ALT_DATA_MESSAGE, 400)
        return decision

    def record(self, input_data: dict, alt_data: dict, granted: bool) -> dict:
        return build_consent(input_data, alt_data, granted)
