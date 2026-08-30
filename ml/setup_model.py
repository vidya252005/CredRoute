"""
Train a credit-risk classifier on the Hugging Face tabular benchmark dataset
(Give Me Some Credit) and export ONNX for Node.js inference.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from datasets import load_dataset
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

HF_DATASET = "inria-soda/tabular-benchmark"
HF_CONFIG = "clf_num_credit"
HF_DATASET_URL = "https://huggingface.co/datasets/inria-soda/tabular-benchmark"

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


def load_credit_data() -> pd.DataFrame:
    dataset = load_dataset(HF_DATASET, HF_CONFIG, split="train")
    return dataset.to_pandas()


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
            ),
        ]
    )


def export_onnx(pipeline: Pipeline) -> None:
    initial_types = [(column, FloatTensorType([None, 1])) for column in FEATURE_COLUMNS]
    onnx_model = convert_sklearn(
        pipeline,
        initial_types=initial_types,
        target_opset=15,
        options={type(pipeline): {"zipmap": False}},
    )
    with open(MODEL_DIR / "credit_risk.onnx", "wb") as handle:
        handle.write(onnx_model.SerializeToString())


def save_metadata(frame: pd.DataFrame, auc: float) -> None:
    medians = frame[FEATURE_COLUMNS].median(numeric_only=True).to_dict()
    metadata = {
        "sourceDataset": f"{HF_DATASET} ({HF_CONFIG})",
        "sourceUrl": HF_DATASET_URL,
        "modelType": "LogisticRegression",
        "framework": "scikit-learn + skl2onnx",
        "target": "SeriousDlqin2yrs (90+ day delinquency within 2 years)",
        "featureColumns": FEATURE_COLUMNS,
        "validationAuc": round(float(auc), 4),
        "trainingMedians": {key: float(value) for key, value in medians.items()},
        "credrouteMapping": {
            "age": "age",
            "MonthlyIncome": "monthlyIncome",
            "DebtRatio": "monthlyObligations / monthlyIncome",
            "RevolvingUtilizationOfUnsecuredLines": "amount / (monthlyIncome * 12)",
            "NumberOfOpenCreditLinesAndLoans": "derived from obligations",
            "NumberOfTimes90DaysLate": "derived from creditScore",
            "NumberOfTime30-59DaysPastDueNotWorse": "derived from creditScore",
            "NumberOfTime60-89DaysPastDueNotWorse": "derived from creditScore",
            "NumberRealEstateLoansOrLines": "derived from loan amount",
            "NumberOfDependents": "default 0",
        },
    }
    with open(MODEL_DIR / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)


def main() -> None:
    print(f"Loading dataset from Hugging Face: {HF_DATASET} [{HF_CONFIG}]")
    frame = load_credit_data()
    features = frame[FEATURE_COLUMNS]
    labels = frame[TARGET_COLUMN].astype(int)

    train_x, test_x, train_y, test_y = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )

    pipeline = build_pipeline()
    pipeline.fit(train_x, train_y)

    probabilities = pipeline.predict_proba(test_x)[:, 1]
    auc = roc_auc_score(test_y, probabilities)
    print(f"Validation ROC-AUC: {auc:.4f}")

    export_onnx(pipeline)
    save_metadata(frame, auc)

    print(f"Saved ONNX model to {MODEL_DIR / 'credit_risk.onnx'}")
    print(f"Saved metadata to {MODEL_DIR / 'metadata.json'}")


if __name__ == "__main__":
    main()
