from app.services.eligibility import evaluate_eligibility


def test_prime_applicant_is_eligible():
    result = evaluate_eligibility(
        {
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
        }
    )
    assert result["eligible"] is True
    assert result["profile"]["segment"] == "prime"
