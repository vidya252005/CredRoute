from app.services.feature_engineering import engineer_features
from app.services.fraud import score_fraud_signals


def test_engineered_credit_ratios():
    features = engineer_features(
        {
            "pan": "ABCDE1234F",
            "age": 30,
            "monthly_income": 100000,
            "income_type": "salaried",
            "cibil_score": 760,
            "existing_emis": 20000,
            "bank_statement_avg_balance": 80000,
            "city_tier": 1,
            "amount": 240000,
            "tenure_months": 24,
        },
        credit_line={"originatedCount": 2, "onTimeRepayments": 2},
    )
    assert features["debtToIncome"] == 0.2
    assert features["emiToIncome"] == features["foir"]
    assert 0 < features["creditUtilisation"] <= 1
    assert features["repaymentConsistency"] == 1.0


def test_fraud_scores_labeled_stacking_and_clean_prime():
    clean = score_fraud_signals(
        {"age": 30, "monthly_income": 90000, "existing_emis": 5000, "amount": 150000, "cibil_score": 780},
        {"fraudProbability": 0.04},
        recent_pans=0,
    )
    fraud = score_fraud_signals(
        {"age": 22, "monthly_income": 18000, "existing_emis": 12000, "amount": 400000, "cibil_score": 510, "rooted": True},
        {"fraudProbability": 0.1},
        recent_pans=22,
    )
    assert clean["blocked"] is False
    assert fraud["fraudProbability"] > clean["fraudProbability"]
    assert fraud["fraudProbability"] >= 0.5
    assert fraud["signals"]
