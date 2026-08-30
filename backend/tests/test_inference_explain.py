from concurrent.futures import ThreadPoolExecutor

from app.services.application_service import score_application
from app.services.risk import predict_with_model


def test_score_includes_explanation_and_decision():
    scored = score_application(
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
            "consent_alt_data": True,
        },
        None,
        None,
        persist_credit_line=False,
    )
    assert scored["decision"]["decision"] in ("approve", "review", "reject")
    risk = scored["risk"]
    assert risk.get("shapFactors") or risk.get("riskFactors")
    assert "engineeredFeatures" in risk
    assert risk["engineeredFeatures"]["debtToIncome"] is not None


def test_inprocess_predictor_and_concurrent_health(client):
    result = predict_with_model(
        {
            "age": 29,
            "monthly_income": 85000,
            "income_type": "salaried",
            "cibil_score": 780,
            "existing_emis": 12000,
            "amount": 300000,
            "tenure_months": 24,
            "bank_statement_avg_balance": 90000,
            "city_tier": 1,
        }
    )
    assert result is not None
    assert result.get("inferenceMode") in ("inprocess", "subprocess")

    def ping(_):
        response = client.get("/api/health")
        return response.status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        codes = list(pool.map(ping, range(32)))
    assert codes.count(200) == 32
