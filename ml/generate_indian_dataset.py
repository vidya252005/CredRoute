"""
Generate a synthetic Indian retail-credit dataset for model training.

Labels simulate 90+ day delinquency using CIBIL, FOIR, income stability, and
city-tier signals — not real bureau data. Intended for portfolio demos only.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = ROOT / "data" / "indian_credit_synthetic.parquet"

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


def late_payment_signal(cibil_score: float, threshold: int) -> float:
    return 1.0 if cibil_score < threshold else 0.0


def applicant_to_features(applicant: dict) -> dict[str, float]:
    monthly_income = max(float(applicant["monthlyIncome"]), 1.0)
    cibil_score = float(applicant.get("cibilScore") or 650)
    existing_emis = float(applicant.get("existingEmis") or 0)
    return {
        "RevolvingUtilizationOfUnsecuredLines": min(
            2.0, float(applicant["amount"]) / (monthly_income * 12.0)
        ),
        "age": float(applicant["age"]),
        "NumberOfTime30-59DaysPastDueNotWorse": late_payment_signal(cibil_score, 680),
        "DebtRatio": min(2.0, existing_emis / monthly_income),
        "MonthlyIncome": monthly_income,
        "NumberOfOpenCreditLinesAndLoans": min(
            15.0,
            round(existing_emis / 4000.0) + (2.0 if float(applicant["tenureMonths"]) >= 24 else 1.0),
        ),
        "NumberOfTimes90DaysLate": late_payment_signal(cibil_score, 620),
        "NumberRealEstateLoansOrLines": 2.0 if float(applicant["amount"]) >= 500000 else 1.0,
        "NumberOfTime60-89DaysPastDueNotWorse": late_payment_signal(cibil_score, 650),
        "NumberOfDependents": float(applicant.get("dependents") or 0),
    }


def default_logit(applicant: dict, features: dict[str, float]) -> float:
    """Hidden data-generating process for synthetic defaults."""
    cibil = float(applicant.get("cibilScore") or 620)
    income_type = applicant.get("incomeType", "salaried")
    city_tier = int(applicant.get("cityTier") or 2)

    logit = -3.8
    logit += (700 - cibil) / 180.0
    logit += features["DebtRatio"] * 1.8
    logit += features["RevolvingUtilizationOfUnsecuredLines"] * 0.9
    logit += features["NumberOfTimes90DaysLate"] * 0.7
    logit += features["NumberOfTime30-59DaysPastDueNotWorse"] * 0.45
    logit += 0.25 if income_type in ("gig", "self_employed") else 0.0
    logit += 0.12 if city_tier >= 3 else 0.0
    logit += 0.08 if applicant.get("thinFile") else 0.0
    logit -= min(features["MonthlyIncome"], 120000) / 80000.0

    return 1.0 / (1.0 + np.exp(-logit))


def generate_applicant(rng: np.random.Generator) -> dict:
    thin_file = rng.random() < 0.12
    income_type = rng.choice(
        ["salaried", "salaried", "salaried", "self_employed", "gig", "msme"],
    )
    monthly_income = int(np.clip(rng.lognormal(10.4, 0.55), 18000, 350000))
    cibil_score = None if thin_file else int(rng.integers(580, 861))
    if thin_file:
        cibil_score = int(rng.integers(300, 680))

    existing_emis = int(monthly_income * rng.uniform(0.05, 0.55))
    amount = int(rng.choice([75000, 150000, 250000, 400000, 600000, 1000000]))
    return {
        "age": int(rng.integers(21, 61)),
        "monthlyIncome": monthly_income,
        "incomeType": income_type,
        "cibilScore": cibil_score,
        "existingEmis": existing_emis,
        "amount": amount,
        "tenureMonths": int(rng.choice([12, 18, 24, 36, 48])),
        "cityTier": int(rng.choice([1, 1, 2, 2, 3])),
        "dependents": int(rng.choice([0, 0, 0, 1, 2])),
        "thinFile": thin_file,
    }


def generate_dataset(n_samples: int = 100000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_samples):
        applicant = generate_applicant(rng)
        features = applicant_to_features(applicant)
        probability = default_logit(applicant, features)
        label = int(rng.random() < probability)
        rows.append({**features, TARGET_COLUMN: label})
    return pd.DataFrame(rows)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    frame = generate_dataset(args.rows, args.seed)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(OUTPUT_PATH, index=False)

    default_rate = frame[TARGET_COLUMN].mean()
    summary = {
        "rows": len(frame),
        "defaultRate": round(float(default_rate), 4),
        "features": FEATURE_COLUMNS,
        "target": TARGET_COLUMN,
        "description": "Synthetic Indian retail credit (portfolio demo only)",
    }
    (OUTPUT_PATH.parent / "indian_credit_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(frame)} rows to {OUTPUT_PATH} (default rate {default_rate:.2%})")


if __name__ == "__main__":
    main()
