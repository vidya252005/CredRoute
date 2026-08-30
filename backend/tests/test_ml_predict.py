"""Smoke tests for the ML inference pipeline."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PREDICT_SCRIPT = ROOT / "ml" / "predict.py"
MODEL_PATH = ROOT / "ml" / "models" / "credit_risk_xgb.joblib"

SAMPLE = {
    "name": "Test User",
    "age": 29,
    "monthlyIncome": 85000,
    "cibilScore": 780,
    "existingEmis": 12000,
    "amount": 300000,
    "tenureMonths": 24,
    "incomeType": "salaried",
    "bankStatementAvgBalance": 90000,
    "cityTier": 1,
}


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="ML model artifacts not found")
def test_predict_script_returns_valid_json():
    result = subprocess.run(
        ["python3", str(PREDICT_SCRIPT)],
        input=json.dumps(SAMPLE),
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert 0 <= payload["defaultProbability"] <= 1
    assert payload["modelSource"] in ("gradient_boosting", "xgboost", "baseline_logistic_regression")
    assert "structuredProbability" in payload
    assert isinstance(payload.get("shapFactors"), list)


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="ML model artifacts not found")
def test_predict_differentiates_risk_profiles():
    prime = {**SAMPLE, "cibilScore": 780, "existingEmis": 5000}
    risky = {**SAMPLE, "cibilScore": 580, "existingEmis": 45000, "amount": 800000}

    def score(payload):
        result = subprocess.run(
            ["python3", str(PREDICT_SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout.strip().splitlines()[-1])["defaultProbability"]

    assert score(risky) > score(prime)
