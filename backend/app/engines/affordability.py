"""Affordability / FOIR engine."""

from __future__ import annotations

from app.domain.borrower import AffordabilityMetrics
from app.domain.context import DecisionContext
from app.services.profile import calculate_foir
from app.services.underwriting_rules import get_platform_rules


class AffordabilityEngine:
    def calculate(self, context: DecisionContext, estimated_rate: float = 14) -> AffordabilityMetrics:
        foir = calculate_foir(context.to_input_data(), estimated_rate)
        income = max(context.financial_profile.monthly_income, 1)
        existing = context.financial_profile.monthly_emi
        disposable = max(0.0, income - existing - foir["proposedEmi"])
        rules = get_platform_rules()
        max_foir = float(rules.get("maxFoir") or 0.6)
        max_affordable_emi = max(0.0, income * max_foir - existing)
        tenure = max(context.application.tenure_months, 1)
        return AffordabilityMetrics(
            foir=foir["foir"],
            disposable_income=disposable,
            max_affordable_emi=max_affordable_emi,
            max_affordable_amount=round(max_affordable_emi * tenure),
            proposed_emi=foir["proposedEmi"],
            total_emi=foir["totalEmi"],
            foir_percent=foir["foirPercent"],
        )
