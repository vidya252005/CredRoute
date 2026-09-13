"""Borrower, credit, and financial profile domain objects."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CreditProfile:
    cibil_score: int | None
    active_loans: int = 0
    active_credit_cards: int = 0
    total_outstanding: int = 0
    credit_utilization: float = 0.0
    repayment_history_score: float = 0.0
    thin_file: bool = False


@dataclass(slots=True)
class FinancialProfile:
    monthly_income: int
    monthly_fixed_expenses: int = 0
    monthly_emi: int = 0
    average_bank_balance: int = 0
    transaction_count: int = 0
    bounce_count: int = 0
    cash_flow_stability: float = 0.0


@dataclass(slots=True)
class AffordabilityMetrics:
    foir: float
    disposable_income: float
    max_affordable_emi: float
    max_affordable_amount: float
    proposed_emi: float = 0.0
    total_emi: float = 0.0
    foir_percent: float = 0.0


@dataclass(slots=True)
class Borrower:
    name: str
    pan: str
    age: int
    employment_type: str
    income: int
    monthly_obligations: int
    city_tier: int
    credit_profile: CreditProfile
    financial_profile: FinancialProfile
    consent_alt_data: bool = False
    android_api_level: int | None = None
    sim_tenure_months: int | None = None
    rooted: bool | None = None
    id: int | None = None
    city: str | None = None


@dataclass(slots=True)
class ApplicationSnapshot:
    requested_amount: int
    tenure_months: int
    product_type: str = "personal_loan"
    id: int | None = None
    status: str | None = None
    financial_notes: str | None = None
