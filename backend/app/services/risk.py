import json
import os
import subprocess
import sys
from pathlib import Path

from app.core.config import settings
from app.core.paths import ml_dir
from app.services.feature_engineering import engineer_features

_ml_module = None
_ml_failed = False


def heuristic_risk(input_data: dict, features: dict | None = None) -> dict:
    engineered = features or engineer_features(input_data)
    cibil = input_data.get("cibil_score") or 580
    credit_risk = max(0, min(1, (760 - cibil) / 300))
    obligation_risk = engineered["obligationRatio"]
    employment_risk = 0.08 if input_data["income_type"] == "salaried" else 0.18
    default_probability = round(
        min(0.85, 0.08 + credit_risk * 0.4 + obligation_risk * 0.35 + employment_risk), 3
    )
    return {
        "defaultProbability": default_probability,
        "fraudProbability": round(min(0.3, 0.02 + obligation_risk * 0.12), 3),
        "confidence": round(0.72 + min(cibil, 850) / 5000, 3),
        "modelSource": "heuristic-fallback",
        "riskBand": "HIGH" if default_probability >= 0.2 else "MEDIUM" if default_probability >= 0.1 else "LOW",
        "riskFactors": ["Heuristic fallback used because ML predictor unavailable"],
        "shapFactors": [],
        "finbertSignal": {"stressScore": 0.5, "signalSource": "none"},
        "engineeredFeatures": engineered,
    }


def _predict_script() -> Path:
    configured = Path(settings.ml_predict_script)
    if configured.is_file():
        return configured
    return ml_dir() / "predict.py"


def _inprocess_predictor():
    global _ml_module, _ml_failed
    if os.environ.get("CREDROUTE_ML_SUBPROCESS") == "1":
        return None
    if _ml_failed:
        return None
    if _ml_module is not None:
        return _ml_module
    try:
        root = str(ml_dir())
        if root not in sys.path:
            sys.path.insert(0, root)
        import predict as ml_predict  # type: ignore

        ml_predict.load_assets()
        _ml_module = ml_predict
        return _ml_module
    except Exception:
        _ml_failed = True
        return None


def _payload(input_data: dict, financial_notes: str | None) -> dict:
    return {
        "age": input_data["age"],
        "monthlyIncome": input_data["monthly_income"],
        "cibilScore": input_data.get("cibil_score"),
        "existingEmis": input_data.get("existing_emis", 0),
        "amount": input_data["amount"],
        "tenureMonths": input_data["tenure_months"],
        "incomeType": input_data["income_type"],
        "bankStatementAvgBalance": input_data.get("bank_statement_avg_balance", 0),
        "cityTier": input_data.get("city_tier", 1),
        "financialNotes": financial_notes,
    }


def predict_with_model(input_data: dict, financial_notes: str | None = None) -> dict | None:
    features = engineer_features(input_data, financial_notes)
    payload = _payload(input_data, financial_notes)
    module = _inprocess_predictor()
    if module is not None:
        try:
            parsed = module.predict(payload)
            parsed["engineeredFeatures"] = features
            parsed["inferenceMode"] = "inprocess"
            return parsed
        except Exception:
            pass

    script = _predict_script()
    if not script.exists():
        return None
    try:
        result = subprocess.run(
            ["python3", str(script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            cwd=str(script.parent),
        )
        parsed = json.loads(result.stdout)
        parsed["engineeredFeatures"] = features
        parsed["inferenceMode"] = "subprocess"
        return parsed
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None


def calculate_risk(input_data: dict, financial_notes: str | None = None) -> dict:
    features = engineer_features(input_data, financial_notes)
    ml_result = predict_with_model(input_data, financial_notes)
    if ml_result is None:
        return heuristic_risk(input_data, features)

    obligation_risk = features["obligationRatio"]
    employment_risk = 0.05 if input_data["income_type"] == "salaried" else 0.14
    cibil = input_data.get("cibil_score") or 580
    default_probability = ml_result["defaultProbability"]
    fraud_probability = round(
        min(
            0.35,
            default_probability * 0.45 + obligation_risk * 0.2 + employment_risk + (0.05 if cibil < 640 else 0),
        ),
        3,
    )
    return {
        "defaultProbability": round(default_probability, 3),
        "structuredProbability": ml_result.get("structuredProbability"),
        "fraudProbability": fraud_probability,
        "confidence": 0.83,
        "modelSource": ml_result.get("modelSource", "ml"),
        "modelAuc": ml_result.get("modelAuc"),
        "riskBand": ml_result.get("riskBand", "MEDIUM"),
        "riskFactors": ml_result.get("riskFactors", []),
        "shapFactors": ml_result.get("shapFactors", []),
        "finbertSignal": ml_result.get("finbertSignal"),
        "engineeredFeatures": features,
        "inferenceMode": ml_result.get("inferenceMode"),
    }
