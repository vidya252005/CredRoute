"""
Train baseline Logistic Regression and boosted tree models.
Compare metrics and persist experiment artifacts.

Usage:
  python3 ml/train_models.py              # US benchmark (legacy)
  python3 ml/train_models.py --dataset indian
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from datasets import load_dataset
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
EXPERIMENTS_DIR = ROOT / "experiments"
INDIAN_DATA_PATH = ROOT / "data" / "indian_credit_synthetic.parquet"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

HF_DATASET = "inria-soda/tabular-benchmark"
HF_CONFIG = "clf_num_credit"

FEATURE_COLUMNS = [
    "RevolvingUtilizationOfUnsecuredLines",
    "age",
    "NumberOfTime30-59DaysPastDueNotWorse",
    "DebtRatio",
    "MonthlyIncome",
    "NumberOfOpenCreditLinesAndLoans",
    "NumberOfTimes90DaysLate",
    "NumberRealEstateLoansOrLines",
    "NumberOfTime60-89DaysPastDueNotWorse",
    "NumberOfDependents",
]
TARGET_COLUMN = "SeriousDlqin2yrs"


def load_boost_classifier():
    """Prefer XGBoost; fall back to sklearn when OpenMP/runtime is unavailable."""
    try:
        from xgboost import XGBClassifier

        return (
            "xgboost",
            XGBClassifier(
                n_estimators=120,
                max_depth=4,
                learning_rate=0.08,
                subsample=0.9,
                colsample_bytree=0.9,
                eval_metric="logloss",
                random_state=42,
                n_jobs=2,
            ),
        )
    except Exception as exc:
        print(
            "XGBoost unavailable — using sklearn GradientBoostingClassifier instead.\n"
            f"  Reason: {exc}\n"
            "  macOS + Anaconda fix: conda install -c conda-forge xgboost libomp\n"
            "  Or: brew install libomp"
        )
        return (
            "gradient_boosting",
            GradientBoostingClassifier(
                n_estimators=120,
                max_depth=4,
                learning_rate=0.08,
                subsample=0.9,
                random_state=42,
            ),
        )


def load_us_credit_data() -> pd.DataFrame:
    dataset = load_dataset(HF_DATASET, HF_CONFIG, split="train")
    return dataset.to_pandas()


def load_indian_credit_data() -> pd.DataFrame:
    if not INDIAN_DATA_PATH.exists():
        from generate_indian_dataset import generate_dataset

        print(f"Indian dataset not found — generating {INDIAN_DATA_PATH}")
        frame = generate_dataset()
        INDIAN_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(INDIAN_DATA_PATH, index=False)
        return frame
    return pd.read_parquet(INDIAN_DATA_PATH)


def kolmogorov_smirnov(labels: np.ndarray, probabilities: np.ndarray) -> float:
    y = np.asarray(labels).astype(int)
    probs = np.asarray(probabilities)
    order = np.argsort(probs)[::-1]
    sorted_labels = y[order]
    n_bad = int(sorted_labels.sum())
    n_good = len(sorted_labels) - n_bad
    if n_bad == 0 or n_good == 0:
        return 0.0
    cum_bad = np.cumsum(sorted_labels) / n_bad
    cum_good = np.cumsum(1 - sorted_labels) / n_good
    return round(float(np.max(np.abs(cum_bad - cum_good))), 4)


def evaluate_model(name: str, probabilities: np.ndarray, labels: np.ndarray) -> dict:
    y = np.asarray(labels).astype(int)
    probs = np.asarray(probabilities)
    preds = (probs >= 0.5).astype(int)
    auc = float(roc_auc_score(y, probs))
    return {
        "model": name,
        "rocAuc": round(auc, 4),
        "gini": round(2 * auc - 1, 4),
        "ks": kolmogorov_smirnov(y, probs),
        "prAuc": round(float(average_precision_score(y, probs)), 4),
        "accuracy": round(float(accuracy_score(y, preds)), 4),
        "f1": round(float(f1_score(y, preds)), 4),
        "precision": round(float(precision_score(y, preds, zero_division=0)), 4),
        "recall": round(float(recall_score(y, preds, zero_division=0)), 4),
        "trainedAt": datetime.now(UTC).isoformat(),
    }


def export_onnx(pipeline: Pipeline) -> None:
    initial_types = [(column, FloatTensorType([None, 1])) for column in FEATURE_COLUMNS]
    onnx_model = convert_sklearn(
        pipeline,
        initial_types=initial_types,
        target_opset=15,
        options={type(pipeline): {"zipmap": False}},
    )
    (MODEL_DIR / "credit_risk.onnx").write_bytes(onnx_model.SerializeToString())


def main() -> None:
    parser = argparse.ArgumentParser(description="Train CredRoute credit-risk models")
    parser.add_argument(
        "--dataset",
        choices=["us", "indian"],
        default="us",
        help="Training dataset: us (HuggingFace benchmark) or indian (synthetic)",
    )
    args = parser.parse_args()

    if args.dataset == "indian":
        print("Loading dataset: Indian synthetic credit (portfolio demo)")
        frame = load_indian_credit_data()
        source_dataset = "credroute/indian-credit-synthetic (portfolio demo)"
    else:
        print(f"Loading dataset: {HF_DATASET} [{HF_CONFIG}]")
        frame = load_us_credit_data()
        source_dataset = f"{HF_DATASET} ({HF_CONFIG})"

    features = frame[FEATURE_COLUMNS]
    labels = frame[TARGET_COLUMN].astype(int)
    default_rate = round(float(labels.mean()), 4)
    print(f"Rows: {len(frame)}, default rate: {default_rate:.2%}")

    train_x, test_x, train_y, test_y = train_test_split(
        features, labels, test_size=0.2, random_state=42, stratify=labels
    )

    lr_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
        ]
    )
    lr_pipeline.fit(train_x, train_y)
    lr_probs = lr_pipeline.predict_proba(test_x)[:, 1]
    lr_metrics = evaluate_model("baseline_logistic_regression", lr_probs, test_y)

    boost_name, boost_model = load_boost_classifier()
    imputer = SimpleImputer(strategy="median")
    train_x_imp = imputer.fit_transform(train_x)
    test_x_imp = imputer.transform(test_x)
    boost_model.fit(train_x_imp, train_y)
    boost_probs = boost_model.predict_proba(test_x_imp)[:, 1]
    boost_metrics = evaluate_model(boost_name, boost_probs, test_y)

    joblib.dump(
        {
            "model": boost_model,
            "imputer": imputer,
            "features": FEATURE_COLUMNS,
            "modelKind": boost_name,
        },
        MODEL_DIR / "credit_risk_xgb.joblib",
    )
    export_onnx(lr_pipeline)

    active_model = (
        boost_name
        if boost_metrics["rocAuc"] + 0.015 >= lr_metrics["rocAuc"]
        else "baseline_logistic_regression"
    )
    medians = frame[FEATURE_COLUMNS].median(numeric_only=True).to_dict()

    metadata = {
        "sourceDataset": source_dataset,
        "datasetKind": args.dataset,
        "defaultRate": default_rate,
        "activeModel": active_model,
        "models": {
            "baseline_logistic_regression": lr_metrics,
            boost_name: boost_metrics,
        },
        "featureColumns": FEATURE_COLUMNS,
        "target": "SeriousDlqin2yrs",
        "trainingMedians": {key: float(value) for key, value in medians.items()},
        "finbertModel": "Vansh180/FinBERT-India-v1",
        "finbertRole": "auxiliary_text_signal_only",
        "modelCard": "ml/MODEL_CARD.md",
    }
    (MODEL_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (EXPERIMENTS_DIR / "comparison.json").write_text(
        json.dumps({"baseline": lr_metrics, boost_name: boost_metrics, "activeModel": active_model}, indent=2),
        encoding="utf-8",
    )

    print(f"Logistic Regression — AUC {lr_metrics['rocAuc']}, Gini {lr_metrics['gini']}, KS {lr_metrics['ks']}")
    print(f"{boost_name} — AUC {boost_metrics['rocAuc']}, Gini {boost_metrics['gini']}, KS {boost_metrics['ks']}")
    print(f"Active model: {active_model}")
    print(f"Saved artifacts under {MODEL_DIR}")


if __name__ == "__main__":
    main()
