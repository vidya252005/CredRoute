"""Structured + auxiliary-text credit-risk inference for CredRoute."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import onnxruntime as ort
import pandas as pd

from explain import explain_structured
from finbert_signal import finbert_signal

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
ONNX_PATH = MODEL_DIR / "credit_risk.onnx"
XGB_PATH = MODEL_DIR / "credit_risk_xgb.joblib"
METADATA_PATH = MODEL_DIR / "metadata.json"

SESSION = None
METADATA = None
XGB_BUNDLE = None


def load_assets() -> None:
    global SESSION, METADATA, XGB_BUNDLE
    if METADATA is None and METADATA_PATH.exists():
        METADATA = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if SESSION is None and ONNX_PATH.exists():
        SESSION = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    if XGB_BUNDLE is None and XGB_PATH.exists():
        XGB_BUNDLE = joblib.load(XGB_PATH)


def late_payment_signal(credit_score: float, threshold: int) -> float:
    if credit_score <= 0:
        return 0.0
    return 1.0 if credit_score < threshold else 0.0


def map_applicant(payload: dict) -> dict[str, float]:
    monthly_income = max(float(payload["monthlyIncome"]), 1.0)
    raw_cibil = payload.get("cibilScore")
    cibil_score = float(raw_cibil) if raw_cibil not in (None, "", 0) else 0.0
    existing_emis = float(payload.get("existingEmis") or payload.get("monthlyObligations") or 0)
    medians = (METADATA or {}).get("trainingMedians", {})

    return {
        "RevolvingUtilizationOfUnsecuredLines": min(
            2.0, float(payload["amount"]) / (monthly_income * 12.0)
        ),
        "age": float(payload["age"]),
        "NumberOfTime30-59DaysPastDueNotWorse": late_payment_signal(cibil_score, 680),
        "DebtRatio": min(2.0, existing_emis / monthly_income),
        "MonthlyIncome": monthly_income,
        "NumberOfOpenCreditLinesAndLoans": min(
            15.0,
            round(existing_emis / 4000.0)
            + (2.0 if float(payload["tenureMonths"]) >= 24 else 1.0),
        ),
        "NumberOfTimes90DaysLate": late_payment_signal(cibil_score, 620),
        "NumberRealEstateLoansOrLines": 2.0 if float(payload["amount"]) >= 500000 else 1.0,
        "NumberOfTime60-89DaysPastDueNotWorse": late_payment_signal(cibil_score, 650),
        "NumberOfDependents": float(medians.get("NumberOfDependents", 0.0)),
    }


def predict_structured(features: dict[str, float]) -> tuple[float, str]:
    load_assets()
    active = (METADATA or {}).get("activeModel", "baseline_logistic_regression")

    if active in ("xgboost", "gradient_boosting") and XGB_BUNDLE is not None:
        try:
            names = XGB_BUNDLE["features"]
            frame = pd.DataFrame([[features[name] for name in names]], columns=names)
            imputed = XGB_BUNDLE["imputer"].transform(frame)
            probability = float(XGB_BUNDLE["model"].predict_proba(imputed)[0][1])
            return max(0.0, min(1.0, probability)), XGB_BUNDLE.get("modelKind", active)
        except Exception:
            # sklearn pickle from an older train can fail on a newer runtime; use ONNX.
            pass

    if SESSION is None:
        raise RuntimeError("No structured risk model available.")

    input_names = [item.name for item in SESSION.get_inputs()]
    canonical = list(features.keys())
    feeds = {}
    for index, name in enumerate(input_names):
        source_key = canonical[index] if index < len(canonical) else name
        feeds[name] = np.array([[float(features[source_key])]], dtype=np.float32)
    outputs = SESSION.run(None, feeds)

    probability = None
    for output in outputs:
        values = np.array(output).reshape(-1)
        if values.size >= 2:
            probability = float(values[1])
            break
        if values.size == 1:
            probability = float(values[0])
    if probability is None:
        raise RuntimeError("Could not parse ONNX model output.")
    return max(0.0, min(1.0, probability)), "baseline_logistic_regression"


def build_risk_factors(features: dict[str, float], finbert: dict) -> list[str]:
    factors = []
    if features["DebtRatio"] > 0.45:
        factors.append("High existing EMI relative to income")
    if features["RevolvingUtilizationOfUnsecuredLines"] > 0.35:
        factors.append("Requested amount is large relative to annual income")
    if features["NumberOfTimes90DaysLate"] > 0:
        factors.append("Weak bureau payment history signal")
    if finbert.get("stressScore", 0.5) > 0.62:
        factors.append("Financial text signal indicates elevated stress")
    if not factors:
        factors.append("No major risk flags in structured or text signals")
    return factors


def predict(payload: dict) -> dict:
    load_assets()
    features = map_applicant(payload)
    structured_probability, model_source = predict_structured(features)

    text = payload.get("financialNotes") or payload.get("financialText")
    finbert = finbert_signal(text)
    fused_probability = max(
        0.0,
        min(1.0, structured_probability * 0.85 + finbert["stressScore"] * 0.15),
    )

    shap_factors = explain_structured(features)
    risk_factors = build_risk_factors(features, finbert)
    band = "HIGH" if fused_probability >= 0.2 else "MEDIUM" if fused_probability >= 0.1 else "LOW"

    return {
        "defaultProbability": round(fused_probability, 4),
        "structuredProbability": round(structured_probability, 4),
        "modelSource": model_source,
        "modelDataset": (METADATA or {}).get("sourceDataset"),
        "modelAuc": (METADATA or {}).get("models", {}).get(model_source, {}).get("rocAuc"),
        "riskBand": band,
        "finbertSignal": finbert,
        "shapFactors": shap_factors,
        "riskFactors": risk_factors,
    }


def main() -> None:
    payload = json.loads(sys.stdin.read())
    print(json.dumps(predict(payload)))


if __name__ == "__main__":
    main()
