"""Local lender eligibility using the specification composition."""

from __future__ import annotations

from app.domain.context import DecisionContext
from app.domain.lender import LenderEligibilityResponse, LenderRecord
from app.domain.specifications import AndSpecification
from app.services.profile import lender_fit_score


class LenderEligibilityEngine:
    def __init__(self, specification: AndSpecification | None = None):
        self.specification = specification or AndSpecification.default_lender_policy()

    def evaluate(self, lender: LenderRecord, context: DecisionContext) -> LenderEligibilityResponse:
        result = self.specification.is_satisfied_by(context, lender)
        profile = (context.eligibility_result.profile if context.eligibility_result else None) or {
            "segment": "near_prime",
            "label": "Near-prime",
        }
        fit = lender_fit_score(
            {
                "serves_thin_file": lender.policy.serves_thin_file,
                "serves_prime": lender.policy.serves_prime,
                "serves_near_prime": lender.policy.serves_near_prime,
            },
            profile,
        )
        return LenderEligibilityResponse(
            eligible=result.passed,
            reason=result.reason,
            fit=fit,
            rejection_reasons=[result.reason] if result.reason and not result.passed else [],
        )
