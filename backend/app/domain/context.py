"""Typed pipeline context: immutable input, derived snapshot, routing view."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.identity import SensitiveIdentity
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


@dataclass(frozen=True)
class ApplicationInput:
    """Immutable applicant ticket. Raw PAN lives only on SensitiveIdentity."""

    name: str
    age: int
    monthly_income: int
    income_type: str
    cibil_score: int | None
    existing_emis: int
    bank_statement_avg_balance: int
    city_tier: int
    amount: int
    tenure_months: int
    consent_alt_data: bool
    identity: SensitiveIdentity
    financial_notes: str | None = None
    android_api_level: int | None = None
    sim_tenure_months: int | None = None
    rooted: bool | None = None

    def with_ticket(self, amount: int, tenure_months: int) -> ApplicationInput:
        return ApplicationInput(
            name=self.name,
            age=self.age,
            monthly_income=self.monthly_income,
            income_type=self.income_type,
            cibil_score=self.cibil_score,
            existing_emis=self.existing_emis,
            bank_statement_avg_balance=self.bank_statement_avg_balance,
            city_tier=self.city_tier,
            amount=amount,
            tenure_months=tenure_months,
            consent_alt_data=self.consent_alt_data,
            identity=self.identity,
            financial_notes=self.financial_notes,
            android_api_level=self.android_api_level,
            sim_tenure_months=self.sim_tenure_months,
            rooted=self.rooted,
        )

    def to_engine_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pan": self.identity.reveal(),
            "age": self.age,
            "monthly_income": self.monthly_income,
            "income_type": self.income_type,
            "cibil_score": self.cibil_score,
            "existing_emis": self.existing_emis,
            "bank_statement_avg_balance": self.bank_statement_avg_balance,
            "city_tier": self.city_tier,
            "amount": self.amount,
            "tenure_months": self.tenure_months,
            "consent_alt_data": self.consent_alt_data,
            "android_api_level": self.android_api_level,
            "sim_tenure_months": self.sim_tenure_months,
            "rooted": self.rooted,
        }

    @classmethod
    def from_dict(cls, input_data: dict[str, Any], financial_notes: str | None = None) -> ApplicationInput:
        return cls(
            name=str(input_data.get("name") or "").strip(),
            age=int(input_data["age"]),
            monthly_income=int(input_data["monthly_income"]),
            income_type=str(input_data.get("income_type") or ""),
            cibil_score=input_data.get("cibil_score"),
            existing_emis=int(input_data.get("existing_emis") or 0),
            bank_statement_avg_balance=int(input_data.get("bank_statement_avg_balance") or 0),
            city_tier=int(input_data.get("city_tier") or 1),
            amount=int(input_data["amount"]),
            tenure_months=int(input_data["tenure_months"]),
            consent_alt_data=bool(input_data.get("consent_alt_data")),
            identity=SensitiveIdentity(str(input_data.get("pan") or "")),
            financial_notes=financial_notes,
            android_api_level=input_data.get("android_api_level"),
            sim_tenure_months=input_data.get("sim_tenure_months"),
            rooted=input_data.get("rooted"),
        )


@dataclass
class DecisionSnapshot:
    risk: RiskResult | None = None
    fraud: FraudResult | None = None
    affordability: AffordabilityMetrics | None = None
    eligibility: EligibilityResult | None = None
    decision: DecisionResult | None = None
    alt_data: AlternativeDataResult | None = None


@dataclass
class RoutingContext:
    application: ApplicationInput
    decision: DecisionSnapshot
    profile: dict[str, Any]
    risk: dict[str, Any]
    financial_notes: str | None = None

    def to_decision_context(self) -> DecisionContext:
        context = DecisionContext.from_input(self.application.to_engine_dict(), self.financial_notes)
        context.eligibility_result = self.decision.eligibility
        context.risk_result = self.decision.risk
        context.fraud_result = self.decision.fraud
        context.alt_data_result = self.decision.alt_data
        context.decision_result = self.decision.decision
        context.affordability = self.decision.affordability
        return context


@dataclass
class DecisionContext:
    """Compatibility facade: engines still receive one object, but input and results are separate."""

    application: ApplicationSnapshot
    borrower: Borrower
    financial_profile: FinancialProfile
    credit_profile: CreditProfile
    financial_notes: str | None = None
    input_data: dict[str, Any] = field(default_factory=dict)
    application_input: ApplicationInput | None = None
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
        if self.application_input:
            return self.application_input.to_engine_dict()
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

    def snapshot(self) -> DecisionSnapshot:
        return DecisionSnapshot(
            risk=self.risk_result,
            fraud=self.fraud_result,
            affordability=self.affordability,
            eligibility=self.eligibility_result,
            decision=self.decision_result,
            alt_data=self.alt_data_result,
        )

    def with_priced_ticket(self, priced_input: dict[str, Any]) -> DecisionContext:
        clone = DecisionContext.from_input(priced_input, self.financial_notes)
        clone.eligibility_result = self.eligibility_result
        clone.risk_result = self.risk_result
        clone.fraud_result = self.fraud_result
        clone.alt_data_result = self.alt_data_result
        clone.decision_result = self.decision_result
        clone.affordability = self.affordability
        clone.credit_line = self.credit_line
        clone.personalized_offer = self.personalized_offer
        clone.consent = self.consent
        return clone

    def routing_context(self, priced_input: dict[str, Any], profile: dict[str, Any], risk: dict[str, Any]) -> RoutingContext:
        source = self.application_input or ApplicationInput.from_dict(self.to_input_data(), self.financial_notes)
        return RoutingContext(
            application=source.with_ticket(int(priced_input["amount"]), int(priced_input["tenure_months"])),
            decision=self.snapshot(),
            profile=profile,
            risk=risk,
            financial_notes=self.financial_notes,
        )

    @classmethod
    def from_input(cls, input_data: dict[str, Any], financial_notes: str | None = None) -> DecisionContext:
        application_input = ApplicationInput.from_dict(input_data, financial_notes)
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
            name=application_input.name,
            pan=application_input.identity.reveal(),
            age=application_input.age,
            employment_type=application_input.income_type,
            income=financial.monthly_income,
            monthly_obligations=financial.monthly_emi,
            city_tier=application_input.city_tier,
            credit_profile=credit,
            financial_profile=financial,
            consent_alt_data=application_input.consent_alt_data,
            android_api_level=application_input.android_api_level,
            sim_tenure_months=application_input.sim_tenure_months,
            rooted=application_input.rooted,
        )
        application = ApplicationSnapshot(
            requested_amount=application_input.amount,
            tenure_months=application_input.tenure_months,
            financial_notes=financial_notes,
        )
        return cls(
            application=application,
            borrower=borrower,
            financial_profile=financial,
            credit_profile=credit,
            financial_notes=financial_notes,
            input_data=application_input.to_engine_dict(),
            application_input=application_input,
        )
