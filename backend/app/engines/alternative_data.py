"""Alternative-data engine — cash-flow and synthetic device-proxy signals."""

from __future__ import annotations

from app.domain.context import DecisionContext
from app.domain.results import AlternativeDataResult
from app.services.alt_data import score_alt_data


class AlternativeDataEngine:
    def evaluate(self, context: DecisionContext) -> AlternativeDataResult:
        input_data = context.to_input_data()
        device_overrides = {
            "androidApiLevel": input_data.get("android_api_level"),
            "simTenureMonths": input_data.get("sim_tenure_months"),
            "rooted": input_data.get("rooted"),
        }
        raw = score_alt_data(input_data, context.credit_line or None, device_overrides)
        score = float(raw.get("altDataScore") or 0)
        return AlternativeDataResult(
            usable=bool(raw.get("used")),
            signals=raw.get("features") or {},
            confidence=score,
            thin_file_eligible=bool(raw.get("thinFileEligible")),
            reasons=list(raw.get("reasons") or []),
            raw=raw,
        )
