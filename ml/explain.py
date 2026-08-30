"""SHAP explainability for structured credit-risk features."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parent
XGB_PATH = ROOT / "models" / "credit_risk_xgb.joblib"


_EXPLAINER = None
_BUNDLE = None


def _tree_explainer():
    global _EXPLAINER, _BUNDLE
    if _EXPLAINER is not None:
        return _EXPLAINER, _BUNDLE
    if not XGB_PATH.exists():
        return None, None
    try:
        import shap

        _BUNDLE = joblib.load(XGB_PATH)
        _EXPLAINER = shap.TreeExplainer(_BUNDLE["model"])
        return _EXPLAINER, _BUNDLE
    except Exception:
        return None, None


def explain_structured(features: dict[str, float], top_k: int = 3) -> list[dict]:
    explainer, bundle = _tree_explainer()
    if explainer is None or bundle is None:
        return _heuristic_explain(features, top_k)

    try:
        feature_names = bundle["features"]
        vector = np.array([[features[name] for name in feature_names]], dtype=np.float32)
        values = explainer.shap_values(vector)
        if isinstance(values, list):
            values = values[1] if len(values) > 1 else values[0]
        pairs = sorted(
            zip(feature_names, values[0], strict=False),
            key=lambda item: abs(item[1]),
            reverse=True,
        )[:top_k]
        return [
            {
                "feature": name,
                "impact": round(float(value), 4),
                "direction": "increases risk" if value > 0 else "reduces risk",
            }
            for name, value in pairs
        ]
    except Exception:
        return _heuristic_explain(features, top_k)


def _heuristic_explain(features: dict[str, float], top_k: int) -> list[dict]:
    candidates = [
        ("DebtRatio", features.get("DebtRatio", 0), "Higher obligation load"),
        ("RevolvingUtilizationOfUnsecuredLines", features.get("RevolvingUtilizationOfUnsecuredLines", 0), "Loan size relative to income"),
        ("NumberOfTimes90DaysLate", features.get("NumberOfTimes90DaysLate", 0), "Severe delinquency signal"),
    ]
    ranked = sorted(candidates, key=lambda item: item[1], reverse=True)[:top_k]
    return [
        {
            "feature": name,
            "impact": round(value, 4),
            "direction": "increases risk" if value > 0 else "reduces risk",
            "detail": detail,
        }
        for name, value, detail in ranked
    ]
