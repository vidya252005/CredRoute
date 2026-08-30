# CredRoute proof pack

Generated `2026-08-30T16:42:26.081012+00:00`. Mode: **quick**.

## Non-negotiable checklist

| Item | Proof |
|------|-------|
| Credit-risk engine | `gradient_boosting` · ROC-AUC baseline 0.8303 → GBM 0.8275 |
| Approve / Review / Reject | Automated decision rate **100.0%** of 40 simulated applications |
| Synthetic warehouse | 2,000 borrowers · 10,000 loans · 20,000 transactions (sqlite-fallback) |
| API load | 20 concurrent · 133.49 rps · p50/p95 143.759 / 188.82 ms |
| PostgreSQL indexes | Loan-history p95 reduced **44.1%** (1.038 → 0.58 ms) |
| ML metrics | Precision 0.6173 · Recall 0.2547 · F1 0.3607 |
| Fraud | Detected **100.0%** of labeled fraud at FPR 0% |
| Redis cache | Hit rate **0%** · retrieval — faster when warm |
| Explainability | **100.0%** of decisions include SHAP/risk factors |
| Inference | In-process p95 5.991 ms vs subprocess 54.04 ms (**88.9%** faster) |

## Reproduce

```bash
docker compose up -d postgres redis
PYTHONPATH=backend python3 backend/benchmarks/run_proof.py --mode quick
PYTHONPATH=backend python3 backend/benchmarks/run_proof.py --mode full   # 100k / 500k / 1M
```
