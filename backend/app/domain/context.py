"""DecisionContext — the shared typed bag passed between engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.borrower import AffordabilityMetrics, ApplicationSnapshot, Borrower, CreditProfile, FinancialProfile
from app.domain.results import (
    AlternativeDataResult,
    DecisionResult,
    EligibilityResult,
    FraudResult,
    RiskResult,
    RoutingResult,
)
from app.services.alt_data import is_thin_file_bureau


@dataclass
class DecisionContext:
    application: ApplicationSnapshot
    borrower: Borrower
    financial_profile: FinancialProfile
    credit_profile: CreditProfile
    financial_notes: str | None = None
    input_data: dict[str, Any] = field(default_factory=dict)
    affordability: AffordabilityMetrics | None = None
    risk_result: RiskResult | None = None
    fraud_result: FraudResult | None = None
    alt_data_result: AlternativeDataResult | None = None
    eligibility_result: EligibilityResult | None = None
    decision_result: DecisionResult | None = None
    routing_result: RoutingResult | None = None
    credit_line: dict[str, Any] = field(default_factory=dict)
    personalized_offer: dict[str, Any] = field(default_factory=dict)
    consent: dict[str, Any] = field(default_factory=dict)
    adverse_action: dict[str, Any] | None = None
    scored_in_ms: int | None = None

    def to_input_data(self) -> dict[str, Any]:
        if self.input_data:
            return dict(self.input_data)
        return {
            "name": self.borrower.name,
            "pan": self.borrower.pan,
            "age": self.borrower.age,
            "monthly_income": self.financial_profile.monthly_income,
            "income_type": self.borrower.employment_type,
            "cibil_score": self.credit_profile.cibil_score,
            "existing_emis": self.financial_profile.monthly_emi,
            "bank_statement_avg_balance": self.financial_profile.average_bank_balance,
            "city_tier": self.borrower.city_tier,
            "amount": self.application.requested_amount,
            "tenure_months": self.application.tenure_months,
            "consent_alt_data": self.borrower.consent_alt_data,
            "android_api_level": self.borrower.android_api_level,
            "sim_tenure_months": self.borrower.sim_tenure_months,
            "rooted": self.borrower.rooted,
        }

    def with_priced_amount(self, amount: int, tenure_months: int) -> dict[str, Any]:
        return {**self.to_input_data(), "amount": amount, "tenure_months": tenure_months}

    @classmethod
    def from_input(cls, input_data: dict[str, Any], financial_notes: str | None = None) -> DecisionContext:
        thin_file = is_thin_file_bureau(input_data)
        credit = CreditProfile(
            cibil_score=input_data.get("cibil_score"),
            thin_file=thin_file,
            total_outstanding=int(input_data.get("existing_emis") or 0),
        )
        financial = FinancialProfile(
            monthly_income=int(input_data["monthly_income"]),
            monthly_emi=int(input_data.get("existing_emis") or 0),
            average_bank_balance=int(input_data.get("bank_statement_avg_balance") or 0),
        )
        borrower = Borrower(
            name=str(input_data.get("name") or ""),
            pan=str(input_data.get("pan") or ""),
            age=int(input_data["age"]),
            employment_type=str(input_data.get("income_type") or ""),
            income=financial.monthly_income,
            monthly_obligations=financial.monthly_emi,
            city_tier=int(input_data.get("city_tier") or 1),
            credit_profile=credit,
            financial_profile=financial,
            consent_alt_data=bool(input_data.get("consent_alt_data")),
            android_api_level=input_data.get("android_api_level"),
            sim_tenure_months=input_data.get("sim_tenure_months"),
            rooted=input_data.get("rooted"),
        )
        application = ApplicationSnapshot(
            requested_amount=int(input_data["amount"]),
            tenure_months=int(input_data["tenure_months"]),
            financial_notes=financial_notes,
        )
        return cls(
            application=application,
            borrower=borrower,
            financial_profile=financial,
            credit_profile=credit,
            financial_notes=financial_notes,
            input_data=dict(input_data),
        )
