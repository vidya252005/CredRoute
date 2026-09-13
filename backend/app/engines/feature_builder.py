"""Stable ML feature boundary — models never read raw database entities."""

from __future__ import annotations

from typing import Any

from app.domain.context import DecisionContext
from app.services.feature_engineering import engineer_features


class FeatureBuilder:
    @staticmethod
    def build(context: DecisionContext) -> dict[str, Any]:
        features = engineer_features(
            context.to_input_data(),
            context.financial_notes,
            context.credit_line or None,
        )
        affordability = context.affordability
        return {
            "income": context.financial_profile.monthly_income,
            "foir": affordability.foir if affordability else features.get("foir"),
            "credit_score": context.credit_profile.cibil_score,
            "utilization": context.credit_profile.credit_utilization or features.get("creditUtilisation"),
            "existing_emis": context.financial_profile.monthly_emi,
            "bank_balance": context.financial_profile.average_bank_balance,
            "city_tier": context.borrower.city_tier,
            "income_type": context.borrower.employment_type,
            "amount": context.application.requested_amount,
            "tenure_months": context.application.tenure_months,
            "thin_file": context.credit_profile.thin_file,
            **features,
        }
