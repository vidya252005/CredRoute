# CredRoute Credit Risk Model Card

> **Portfolio demo only.** Mock lenders, synthetic data, no real bureau feeds or production lending decisions.

## Model overview

| Field | Value |
|-------|-------|
| **Task** | Binary classification — predict 90+ day delinquency within 2 years |
| **Primary model** | Gradient Boosting (XGBoost preferred; sklearn GBM fallback) |
| **Baseline** | Logistic Regression (exported as ONNX) |
| **Inference** | `ml/predict.py` — structured model + optional FinBERT text signal (15%) |
| **Explainability** | SHAP top-3 contributors + rule-based risk factor strings |

## Training data

### Recommended: Indian synthetic dataset

```bash
python3 ml/generate_indian_dataset.py --rows 100000
python3 ml/train_models.py --dataset indian
```

- **Source:** `ml/data/indian_credit_synthetic.parquet`
- **Population:** Synthetic Indian borrowers (CIBIL 300–860, ₹18k–₹3.5L income, salaried/gig/MSME)
- **Label:** Simulated default using CIBIL, FOIR, income type, city tier (not real outcomes)
- **Default rate:** ~8–12% (class-imbalanced, realistic for retail credit)

### Legacy: US benchmark dataset

```bash
python3 ml/train_models.py --dataset us   # default
```

- **Source:** Hugging Face [`inria-soda/tabular-benchmark`](https://huggingface.co/datasets/inria-soda/tabular-benchmark) (`clf_num_credit`)
- **Original:** Kaggle *Give Me Some Credit* (~150k US borrowers)
- **Note:** Applicant fields are heuristically mapped from Indian form inputs — use `--dataset indian` for domain alignment

## Evaluation metrics (hold-out 20%, stratified)

Metrics are logged to `ml/models/metadata.json` after training:

| Metric | Purpose |
|--------|---------|
| **ROC-AUC** | Ranking quality (primary model selection metric) |
| **Gini** | `2 × AUC − 1` — common credit-scoring convention |
| **KS** | Kolmogorov–Smirnov separation between good/bad distributions |
| **Precision / Recall / F1** | At 0.5 probability threshold |
| **Accuracy** | Reported for completeness; less meaningful on imbalanced defaults |
| **PR-AUC** | Precision–recall area under curve |

## Feature mapping (applicant → model)

| Model feature | CredRoute input |
|---------------|-----------------|
| `MonthlyIncome` | `monthlyIncome` |
| `DebtRatio` | `existingEmis / monthlyIncome` |
| `RevolvingUtilizationOfUnsecuredLines` | `amount / (monthlyIncome × 12)` |
| `NumberOfTimes90DaysLate` | CIBIL &lt; 620 → 1 |
| `NumberOfTime30-59DaysPastDueNotWorse` | CIBIL &lt; 680 → 1 |
| `NumberOfTime60-89DaysPastDueNotWorse` | CIBIL &lt; 650 → 1 |
| `NumberOfOpenCreditLinesAndLoans` | Derived from EMIs + tenure |
| `NumberRealEstateLoansOrLines` | Loan amount ≥ ₹5L → 2 |
| `age` | `age` |
| `NumberOfDependents` | Training median (0) unless supplied |

## Decision integration

ML output feeds the decision engine (`backend/app/services/decision_engine.py`):

- **Approve:** Low default probability, no fraud block
- **Review:** Borderline risk or elevated fraud signals
- **Reject:** High default probability or hard fraud block

See [`docs/PROOF.md`](../docs/PROOF.md) for inference p95, automated decision rate, fraud precision/recall, cache hit rate, and warehouse index speedup.

Thin-file applicants (no CIBIL or CIBIL &lt; 650) are underwritten on cash-flow plus a synthetic device/SIM proxy and a first-loan credit line. Bureau PD is advisory on that path.

## Limitations & known gaps

1. **Not production-ready for real lending** — synthetic labels, no regulatory validation
2. **Feature mapping is approximate** — CIBIL thresholds proxy US delinquency flags
3. **FinBERT is auxiliary** — keyword fallback when torch/transformers unavailable
4. **No fairness audit** — segment parity (thin-file, tier-3) not formally measured
5. **Drift detection is MVP** — median deviation vs training; PSI bins planned
6. **Subprocess inference** — `python3 ml/predict.py`; in-process ONNX planned

## Monitoring

- **Admin dashboard:** `/api/admin/ml/metrics` — model comparison, active model, dataset
- **Per-evaluation drift:** `risk.drift.driftAlert` when average feature drift ≥ 35%
- **Audit events:** `risk_scored`, `decision_made` persisted per application

## Retraining

```bash
npm run ml:indian    # generate Indian data + train
npm run ml:train     # US benchmark (legacy)
```

Artifacts: `ml/models/credit_risk_xgb.joblib`, `credit_risk.onnx`, `metadata.json`, `experiments/comparison.json`

## Author & intended use

Built as a **fintech portfolio project** demonstrating credit decisioning architecture: eligibility → ML risk → fraud → decision → lender mesh → offer ranking. Suitable for technical interviews and architecture discussions; not for regulated lending without full validation on real labeled data.
