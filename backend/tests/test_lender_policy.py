import asyncio

from app.data.lenders import LENDER_SEED
from app.lenders.base import MockLenderProvider
from app.services.lender_policy import check_hard_policy_gates, normalize_lender_policy
from app.services.profile import classify_profile


def test_borderline_profile_only_qualifies_for_lender_c():
    input_data = {
        "name": "Borderline Applicant",
        "pan": "ABCDE1234F",
        "age": 29,
        "monthly_income": 22000,
        "income_type": "salaried",
        "cibil_score": 615,
        "existing_emis": 0,
        "bank_statement_avg_balance": 20000,
        "city_tier": 1,
        "amount": 300000,
        "tenure_months": 24,
    }
    profile = classify_profile(input_data)
    provider = MockLenderProvider("LENDER-C-MOCK")

    async def run_checks() -> list[str]:
        approved = []
        for seed in LENDER_SEED:
            lender = {"id": 1, **seed}
            result = await provider.check_eligibility(lender, input_data, profile)
            if result["eligible"]:
                approved.append(lender["code"])
        return approved

    assert asyncio.run(run_checks()) == ["LENDER-C-MOCK"]


def test_missing_cibil_fails_prime_lenders():
    input_data = {
        "amount": 100000,
        "monthly_income": 80000,
        "cibil_score": None,
        "income_type": "salaried",
        "tenure_months": 12,
        "city_tier": 1,
        "existing_emis": 0,
        "bank_statement_avg_balance": 50000,
    }
    axis = normalize_lender_policy(LENDER_SEED[0])
    result = check_hard_policy_gates(axis, input_data, "AxisBankMock")
    assert result is not None
    assert result["eligible"] is False


def test_missing_policy_thresholds_fail_closed():
    result = check_hard_policy_gates(normalize_lender_policy({"name": "BrokenMock"}), {"amount": 1, "monthly_income": 1}, "BrokenMock")
    assert result is not None
    assert result["eligible"] is False
