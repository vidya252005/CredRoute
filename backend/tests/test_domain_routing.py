"""Domain objects, specifications, and routing strategy tests."""

from app.domain.context import DecisionContext
from app.domain.lender import LenderPolicy, LenderRecord
from app.domain.results import LenderOffer
from app.domain.specifications import (
    AmountSpecification,
    AndSpecification,
    CreditScoreSpecification,
    IncomeSpecification,
)
from app.engines.consent import ConsentService
from app.resilience.circuit_breaker import CircuitBreaker
from app.resilience.retry import RetryPolicy
from app.routing.candidate import CandidateSelector
from app.routing.normalizer import OfferNormalizer
from app.routing.strategies import BestApprovalStrategy, LowestCostStrategy, resolve_strategy
from app.services.circuit_breaker import _states


def _context(**overrides) -> DecisionContext:
    payload = {
        "name": "Aarav",
        "pan": "ABCDE1234F",
        "age": 29,
        "monthly_income": 85000,
        "income_type": "salaried",
        "cibil_score": 780,
        "existing_emis": 12000,
        "bank_statement_avg_balance": 90000,
        "city_tier": 1,
        "amount": 300000,
        "tenure_months": 24,
        "consent_alt_data": True,
    }
    payload.update(overrides)
    return DecisionContext.from_input(payload)


def _lender(**overrides) -> LenderRecord:
    raw = {
        "id": 1,
        "code": "AXISBANK-MOCK",
        "name": "AxisBankMock",
        "min_income": 30000,
        "min_credit_score": 700,
        "max_amount": 1500000,
        "max_foir": 0.55,
        "base_interest_rate": 12.5,
        "serves_prime": True,
        "serves_near_prime": False,
        "serves_thin_file": False,
        "income_types": ["salaried", "self_employed"],
        "city_tiers": [1, 2, 3],
    }
    raw.update(overrides)
    return LenderRecord(
        id=int(raw["id"]),
        code=raw["code"],
        name=raw["name"],
        active=True,
        category="bank",
        policy=LenderPolicy.from_lender_dict(raw),
        raw=raw,
    )


def test_decision_context_from_input():
    context = _context()
    assert context.borrower.pan == "ABCDE1234F"
    assert context.application_input is not None
    assert context.application_input.identity.pan_masked == "ABCXX1234X"
    assert context.snapshot().risk is None
    priced = context.with_priced_amount(150000, 12)
    routing = context.routing_context(priced, {"segment": "prime"}, {"defaultProbability": 0.1})
    assert routing.application.amount == 150000
    assert routing.decision.eligibility is None
    assert context.credit_profile.cibil_score == 780
    assert context.financial_profile.monthly_income == 85000
    assert context.to_input_data()["amount"] == 300000


def test_credit_score_spec_rejects_thin_file_on_prime_lender():
    context = _context(cibil_score=None)
    result = CreditScoreSpecification().is_satisfied_by(context, _lender())
    assert result.passed is False


def test_income_and_amount_specs():
    context = _context(monthly_income=20000, amount=2000000)
    assert IncomeSpecification().is_satisfied_by(context, _lender()).passed is False
    assert AmountSpecification().is_satisfied_by(context, _lender()).passed is False


def test_and_specification_short_circuits():
    context = _context(monthly_income=10000)
    result = AndSpecification.default_lender_policy().is_satisfied_by(context, _lender())
    assert result.passed is False
    assert result.reason


def test_candidate_selector_skips_amount_mismatches():
    context = _context(amount=2000000)
    selected = CandidateSelector().select([_lender(max_amount=500000)], context)
    assert selected == []


def test_offer_normalizer_accepts_lender_specific_keys():
    offer = OfferNormalizer().normalize(
        {"lenderId": 1, "lenderCode": "HDFC", "lenderName": "HDFC", "roi": 13.5, "procFee": 2999, "approvalProbability": 0.8, "maxAmount": 100000}
    )
    assert offer.interest_rate == 13.5
    assert offer.processing_fee == 2999


def test_routing_strategies():
    cheap = LenderOffer(1, "A", "A", 11.0, 0, 0.7, 100000, score=0.5)
    likely = LenderOffer(2, "B", "B", 16.0, 0, 0.95, 100000, score=0.9)
    assert LowestCostStrategy().select([cheap, likely]).lender_code == "A"
    assert BestApprovalStrategy().select([cheap, likely]).lender_code == "B"
    assert resolve_strategy("balanced").name == "balanced"


def test_consent_service_requires_grant():
    from app.core.exceptions import AppError

    try:
        ConsentService().require_alt_data(False)
        raise AssertionError("expected consent error")
    except AppError as error:
        assert error.code == "CONSENT_REQUIRED"


def test_retry_policy_delay_is_bounded():
    policy = RetryPolicy(base_delay_ms=40, max_delay_ms=80)
    assert 0 < policy.delay_seconds(5) <= 0.08 * 1.5


def test_circuit_breaker_class_delegates():
    from app.core.cache import cache_delete

    cache_delete("credroute:cb:TEST-LENDER")
    _states.pop("TEST-LENDER", None)
    breaker = CircuitBreaker("TEST-LENDER", failure_threshold=2, recovery_timeout_ms=50)
    assert breaker.allow_request() is True
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.allow_request() is False
    breaker.record_success()
    assert breaker.allow_request() is True
