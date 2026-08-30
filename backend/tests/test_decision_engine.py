from app.services.alt_data import score_alt_data
from app.services.decision_engine import evaluate_decision
from app.services.offer_pricing import price_offer


def test_rejects_high_default_probability():
    eligibility = {"eligible": True, "profile": {"segment": "near_prime"}}
    risk = {"defaultProbability": 0.4, "fraudProbability": 0.05, "riskBand": "HIGH", "riskFactors": [], "shapFactors": []}
    fraud = {"fraudProbability": 0.05, "signals": [], "blocked": False}
    result = evaluate_decision(eligibility, risk, fraud)
    assert result["decision"] == "reject"


def test_reviews_borderline_risk():
    eligibility = {"eligible": True, "profile": {"segment": "near_prime"}}
    risk = {"defaultProbability": 0.2, "fraudProbability": 0.08, "riskBand": "MEDIUM", "riskFactors": [], "shapFactors": []}
    fraud = {"fraudProbability": 0.08, "signals": [], "blocked": False}
    result = evaluate_decision(eligibility, risk, fraud)
    assert result["decision"] == "review"


def test_approves_clean_profile():
    eligibility = {"eligible": True, "profile": {"segment": "prime"}}
    risk = {"defaultProbability": 0.08, "fraudProbability": 0.03, "riskBand": "LOW", "riskFactors": [], "shapFactors": []}
    fraud = {"fraudProbability": 0.03, "signals": [], "blocked": False}
    result = evaluate_decision(eligibility, risk, fraud)
    assert result["decision"] == "approve"


def test_thin_file_uses_alt_data_not_bureau_pd():
    eligibility = {"eligible": True, "profile": {"segment": "thin_file"}}
    risk = {"defaultProbability": 0.45, "fraudProbability": 0.04, "riskBand": "HIGH", "riskFactors": [], "shapFactors": []}
    fraud = {"fraudProbability": 0.04, "signals": [], "blocked": False}
    alt_data = {
        "used": True,
        "thinFileEligible": True,
        "altDataScore": 0.78,
        "reasons": ["Bank-balance coverage 110% of monthly income"],
    }
    result = evaluate_decision(eligibility, risk, fraud, alt_data)
    assert result["decision"] == "approve"


def test_thin_file_rejects_weak_alt_data():
    eligibility = {"eligible": True, "profile": {"segment": "thin_file"}}
    risk = {"defaultProbability": 0.2, "riskBand": "MEDIUM"}
    fraud = {"fraudProbability": 0.04, "signals": [], "blocked": False}
    alt_data = {"used": True, "thinFileEligible": False, "altDataScore": 0.3, "reasons": ["Rooted-device proxy flagged"]}
    result = evaluate_decision(eligibility, risk, fraud, alt_data)
    assert result["decision"] == "reject"


def test_alt_data_scores_cashflow():
    result = score_alt_data(
        {
            "pan": "FGHIJ5678K",
            "monthly_income": 28000,
            "existing_emis": 4000,
            "bank_statement_avg_balance": 32000,
            "income_type": "gig",
            "city_tier": 2,
            "cibil_score": None,
        },
        device_overrides={"rooted": False, "simTenureMonths": 24, "androidApiLevel": 33},
    )
    assert result["used"] is True
    assert result["thinFileEligible"] is True
    assert result["altDataScore"] >= 0.55


def test_personalized_offer_does_not_cap_prime_to_thin_file_line():
    priced = price_offer(
        {"amount": 300000, "tenure_months": 24, "monthly_income": 85000},
        {"defaultProbability": 0.08, "riskBand": "LOW"},
        {"altDataScore": 0.5},
        {"currentLimit": 40000, "nextLimit": 60000, "firstLoan": True},
        "prime",
    )
    assert priced["offeredAmount"] == 300000
    assert priced["capped"] is False


def test_personalized_offer_caps_thin_file_first_loan():
    priced = price_offer(
        {"amount": 300000, "tenure_months": 24, "monthly_income": 28000},
        {"defaultProbability": 0.25, "riskBand": "HIGH"},
        {"altDataScore": 0.72},
        {"currentLimit": 40000, "nextLimit": 60000, "firstLoan": True},
        "thin_file",
    )
    assert priced["capped"] is True
    assert priced["offeredAmount"] <= 40000
    assert priced["tenureMonths"] <= 12
    assert 16 <= priced["apr"] <= 24
