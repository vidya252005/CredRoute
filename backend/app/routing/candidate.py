"""Pre-filter lenders before any outbound provider call."""

from __future__ import annotations

from app.domain.context import DecisionContext
from app.domain.lender import LenderRecord


class CandidateSelector:
    def select(self, lenders: list[LenderRecord], context: DecisionContext) -> list[LenderRecord]:
        amount = context.application.requested_amount
        product = context.application.product_type
        return [
            lender
            for lender in lenders
            if lender.active and lender.supports_product(product) and lender.supports_amount(amount)
        ]
