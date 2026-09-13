"""Normalize lender-specific offer payloads into LenderOffer."""

from __future__ import annotations

from typing import Any

from app.domain.results import LenderOffer


class OfferNormalizer:
    def normalize(self, payload: dict[str, Any]) -> LenderOffer:
        if "interestRate" not in payload and "roi" in payload:
            payload = {
                **payload,
                "interestRate": payload.get("roi"),
                "processingFee": payload.get("procFee", payload.get("processingFee", 0)),
            }
        if "interestRate" not in payload and "interest_rate" in payload:
            payload = {
                **payload,
                "interestRate": payload.get("interest_rate"),
                "processingFee": payload.get("processing_fee", 0),
                "approvalProbability": payload.get("approval_probability", payload.get("approvalProbability", 0)),
                "lenderCode": payload.get("lender_code", payload.get("lenderCode")),
                "lenderName": payload.get("lender_name", payload.get("lenderName")),
                "lenderId": payload.get("lender_id", payload.get("lenderId")),
                "maxAmount": payload.get("max_amount", payload.get("maxAmount", 0)),
            }
        return LenderOffer.from_dict(payload)
