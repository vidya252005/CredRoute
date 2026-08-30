# CredRoute proof pack

Last harness run: **2026-08-30** · mode **quick** (SQLite on this machine).  
Regenerate: `npm run bench` · Full scale (100k / 500k / 1M + 100/250/500 concurrent): `docker compose up -d postgres redis && npm run bench:full`

Raw JSON: `benchmarks/results/PROOF.json` after a harness run.

---

## 1. Non-negotiable checklist

| Item | Status | Measured proof |
|------|--------|----------------|
| Credit-risk engine | Done | GBM in-process via `ml/predict.py` · structured PD + FOIR + utilisation |
| Approve / Review / Reject | Done | Configurable rules in `underwriting_rules.json` · **100%** automated (approve+reject) on 40 mixed applicants |
| 100k users / 500k loans | Harness | `npm run bench:full` loads warehouse; quick run used **2,000 / 10,000 / 20,000** |
| API load testing | Done | Locust file + harness: **20 concurrent**, **157.6 rps**, **0% errors** |
| p50 / p95 / p99 | Done | Health API p50 **118.6 ms** · p95 **161.6 ms** · p99 **183.0 ms** |
| Postgres indexes + before/after | Done | Loan-history join p95 **0.543 → 0.315 ms (−42%)** on quick warehouse |
| ML ROC-AUC / Precision / Recall | Done | LR AUC **0.830** · GBM AUC **0.828**, precision **0.617**, recall **0.255**, accuracy **0.871** |
| Fraud detection | Done | Rule + velocity/stacking/device · **100%** of labeled synthetic fraud personas at **0% FPR** (same-rule labels) |
| Redis cache + hit rate | Instrumented | `/api/metrics` exposes `cacheHitRate`; this run had Redis **off** (graceful miss). Re-run with Redis up. |
| Automated tests + coverage | Done | **34** pytest cases · `npm run test:api` adds `--cov=app` · CI on every push |

---

## 2. API / backend performance

Quick harness (`GET /api/health`, TestClient, 80 requests, 20 workers):

| Metric | Value |
|--------|-------|
| p50 | 118.6 ms |
| p95 | 161.6 ms |
| p99 | 183.0 ms |
| Requests/sec | 157.6 |
| Error rate | 0% |
| Timeout rate | 0% |

Scale-up (Postgres + live uvicorn):

```bash
npm run bench:full          # 100 / 250 / 500 concurrent in-process
npm run load                # Locust against :8000
```

---

## 3. Database performance

Warehouse tables: `warehouse_borrowers`, `warehouse_loans`, `warehouse_transactions`, `warehouse_applications`.  
Query: PAN → loans JOIN transactions (the loan-history endpoint).

| Mode | Borrowers | Loans | Transactions | Applications |
|------|-----------|-------|--------------|--------------|
| quick | 2,000 | 10,000 | 20,000 | 500 |
| full | 100,000 | 500,000 | 1,000,000 | 10,000 |

Quick index proof: **−42% p95** on the history join after `ix_wh_loans_borrower_originated` + `ix_wh_txn_loan_posted` + `ix_wh_borrowers_pan`.

OLTP indexes (Alembic `003` / `004`): `loan_applications(borrower_profile_id, status, created_at)`, `application_events(event_type, created_at)`.

Connection pool: `pool_size=20`, `max_overflow=40`, `pool_pre_ping=True`.

---

## 4. Credit decisioning

Rules live in `backend/app/data/underwriting_rules.json` (not hardcoded in Python).

Per application the engine computes:

- Credit/risk score (GBM PD)
- Debt-to-income (`existing_emis / income`)
- EMI-to-income (FOIR, existing + proposed EMI)
- Credit utilisation (`amount / (income × 12)`)
- Repayment consistency (on-time / originated on the PAN line)
- Approve / Review / Reject

Quick batch: **36 approve · 0 review · 4 reject** → **100% automated** (no manual-review bucket in this mix).

---

## 5. ML / inference

| Model | ROC-AUC | Precision | Recall | Accuracy | Role |
|-------|---------|-----------|--------|----------|------|
| Logistic regression (ONNX) | 0.830 | 0.344 | 0.752 | 0.760 | Baseline |
| Gradient boosting | 0.828 | 0.617 | 0.255 | 0.871 | **Active** |

GBM is selected for **accuracy and precision at the operating point**, not raw AUC (LR wins AUC by 0.003). Indian synthetic mapping is the feature-engineering step vs the US Give-Me-Some-Credit layout.

Inference (warm):

| Path | p50 | p95 |
|------|-----|-----|
| Subprocess `python3 ml/predict.py` | 47.8 ms | 50.7 ms |
| In-process preloaded model | 13.0 ms | **14.1 ms** |

**−72% p95** by preloading the model instead of spawning a process per request. Concurrent 16 predictions ≈ **60 pred/s**.

Dataset generator default is now **100,000** rows (`python3 ml/generate_indian_dataset.py --rows 100000`).

---

## 6. Fraud

Signals: PAN velocity, stacking window, young+weak CIBIL, EMI load, ticket vs income, rooted-device proxy.

Labeled synthetic personas (clean prime vs stacking/mule) at threshold 0.25:

- Precision **1.00** · Recall **1.00** · FPR **0%** · FNR **0%**
- These labels are **constructed from the same rules** — use them as a regression test, not as a bureau-fraud AUC claim.

---

## 7. Explainability

SHAP explainer is **cached** (not rebuilt per request). Heuristic factors if SHAP is unavailable.

Quick batch: **100%** of decisions had `shapFactors` and/or `riskFactors`. Positive vs negative impact is the `direction` field (`increases risk` / `reduces risk`).

---

## 8. Caching

Risk scores cache in Redis (`risk:{pan}:…`, TTL 120s). Stats on `GET /api/metrics`.

- Hits/misses recorded even when Redis is down (treated as misses; API still works).
- Invalidation: `cache_delete`.
- This harness run: Redis **unavailable** → 0% hit rate (expected). With Redis: `npm run bench` after `docker compose up -d redis`.

---

## 9. Events (no Kafka)

Redis Streams stream `credroute.events`:

- `LoanApplicationCreated`
- `RiskEvaluationCompleted`
- `LoanDecisionGenerated`

Published after a successful evaluate. Kafka is omitted on purpose — Redis is already in the stack.

---

## 10. Testing, CI, production engineering

- Unit + integration + ML smoke + concurrent health (16 threads)
- `npm run test:api` → pytest-cov
- GitHub Actions: Node tests, `npm run build`, pytest+coverage, **quick proof harness**, Postgres + Redis services
- Docker: `backend/Dockerfile` · Compose for api/worker/postgres/redis
- Health: `GET /api/health` (postgres + redis flags)
- Prometheus: `GET /metrics` and `GET /api/metrics/prometheus`
- OpenAPI: `http://localhost:8000/docs`
- Structured JSON logs from the FastAPI process
- Locust: unique PAN + consent per evaluate (avoids stacking false positives)

---

## Target one-liners (resume)

- Automated **100%** of 40 mixed simulated loan decisions through rule + ML underwriting.
- Reduced risk-model inference p95 from **50.7 ms → 14.1 ms (−72%)** by preloading the model.
- Provided explainable risk factors for **100%** of those decisions.
- Reduced loan-history join p95 by **42%** after adding borrower/loan/transaction indexes (quick warehouse; re-run `--mode full` on Postgres for 500k+ loans).
- Detected **100%** of constructed fraudulent personas at **0%** false-positive rate on the rule suite.
- API proof: **158 rps** at 20 concurrent, **0%** errors (health); Locust + `bench:full` for 100/250/500.
