"""Composable lender-eligibility specifications."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.domain.context import DecisionContext
from app.domain.lender import LenderRecord
from app.services.lender_policy import resolve_cibil
from app.services.profile import calculate_foir, lender_fit_score


@dataclass(slots=True)
class SpecResult:
    passed: bool
    reason: str | None = None


class Specification(ABC):
    @abstractmethod
    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        raise NotImplementedError


class CreditScoreSpecification(Specification):
    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        policy = lender.policy
        min_score = policy.min_credit_score
        if not min_score or min_score <= 0:
            return SpecResult(True)
        cibil = resolve_cibil(context.to_input_data())
        if cibil is None:
            if policy.serves_thin_file:
                return SpecResult(True)
            return SpecResult(False, f"{lender.name} requires a bureau score (minimum {min_score})")
        if cibil < min_score:
            return SpecResult(False, f"CIBIL {cibil} below {lender.name} threshold ({min_score})")
        return SpecResult(True)


class IncomeSpecification(Specification):
    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        if lender.policy.min_income is None:
            return SpecResult(False, f"{lender.name} policy incomplete (min_income)")
        income = context.financial_profile.monthly_income
        if income < lender.policy.min_income:
            return SpecResult(
                False, f"Monthly income below {lender.name} minimum (₹{lender.policy.min_income:,})"
            )
        return SpecResult(True)


class AmountSpecification(Specification):
    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        if lender.policy.max_amount is None:
            return SpecResult(False, f"{lender.name} policy incomplete (max_amount)")
        amount = context.application.requested_amount
        if amount > lender.policy.max_amount:
            return SpecResult(
                False,
                f"Requested amount exceeds {lender.name} max ticket size (₹{lender.policy.max_amount:,})",
            )
        if lender.policy.min_amount is not None and amount < lender.policy.min_amount:
            return SpecResult(False, f"Requested amount below {lender.name} minimum ticket size")
        return SpecResult(True)


class FOIRSpecification(Specification):
    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        foir = calculate_foir(context.to_input_data(), lender.policy.base_interest_rate)
        if foir["foir"] > lender.policy.max_foir:
            return SpecResult(False, f"FOIR {foir['foirPercent']}% exceeds {lender.name} cap")
        return SpecResult(True)


class CityTierSpecification(Specification):
    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        tiers = lender.policy.accepted_city_tiers
        if tiers and context.borrower.city_tier not in tiers:
            return SpecResult(False, f"{lender.name} does not serve tier-{context.borrower.city_tier} cities")
        return SpecResult(True)


class IncomeTypeSpecification(Specification):
    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        allowed = lender.policy.accepted_income_types
        income_type = context.borrower.employment_type
        if allowed and income_type not in allowed:
            return SpecResult(False, f"{lender.name} does not serve {income_type} profiles")
        return SpecResult(True)


class ThinFileSpecification(Specification):
    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        profile = (context.eligibility_result.profile if context.eligibility_result else None) or {}
        segment = profile.get("segment")
        if segment != "thin_file" or not lender.policy.serves_thin_file:
            return SpecResult(True)
        income = max(context.financial_profile.monthly_income, 1)
        if context.financial_profile.average_bank_balance < income * 0.8:
            return SpecResult(False, "Insufficient alternate bank-statement data for thin-file routing")
        return SpecResult(True)


class ProfileFitSpecification(Specification):
    def __init__(self, minimum: float = 0.4):
        self.minimum = minimum

    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
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
        if fit < self.minimum:
            return SpecResult(False, f"{lender.name} is not a fit for {profile.get('label', 'this')} applicants")
        return SpecResult(True)


class PolicyCompleteSpecification(Specification):
    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        missing = [
            key
            for key, value in (
                ("min_income", lender.policy.min_income),
                ("max_amount", lender.policy.max_amount),
                ("min_credit_score", lender.policy.min_credit_score),
            )
            if value is None
        ]
        if missing:
            return SpecResult(False, f"{lender.name} policy incomplete ({', '.join(missing)})")
        return SpecResult(True)


@dataclass
class AndSpecification(Specification):
    specs: list[Specification] = field(default_factory=list)

    def is_satisfied_by(self, context: DecisionContext, lender: LenderRecord) -> SpecResult:
        reasons: list[str] = []
        for spec in self.specs:
            result = spec.is_satisfied_by(context, lender)
            if not result.passed:
                reasons.append(result.reason or "Policy not satisfied")
                return SpecResult(False, reasons[0])
        return SpecResult(True)

    @classmethod
    def default_lender_policy(cls) -> AndSpecification:
        return cls(
            [
                PolicyCompleteSpecification(),
                AmountSpecification(),
                IncomeSpecification(),
                CreditScoreSpecification(),
                IncomeTypeSpecification(),
                CityTierSpecification(),
                ProfileFitSpecification(),
                ThinFileSpecification(),
                FOIRSpecification(),
            ]
        )
