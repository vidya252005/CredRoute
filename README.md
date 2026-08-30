# CredRoute

**Digital Lending Marketplace & Credit Decisioning Platform**

A production-style fintech portfolio project: eligibility engine, ML credit scoring, fraud detection, lender orchestration, and offer ranking — built for Indian retail lending workflows.

> Mock lenders only · Synthetic data only · No real banks, NBFCs, or credit bureaus.

---

## Why this project

This is not a CRUD app with an ML label. It demonstrates how a **digital lending marketplace** actually works:

| Capability | Implementation |
|------------|----------------|
| **Credit decisioning** | Eligibility → ML risk → fraud → Approve/Review/Reject decision engine |
| **ML pipeline** | Train/compare models, ONNX export, SHAP explainability, FinBERT text signal |
| **Lender orchestration** | Parallel mock lender mesh, circuit breaker, retries, weighted offer ranking |
| **Production patterns** | JWT auth, PostgreSQL, Redis cache, idempotency keys, Alembic migrations, audit events |
| **Ops & monitoring** | Admin console, ML metrics dashboard, feature drift alerts, Prometheus scaffold |
| **India-specific logic** | CIBIL, PAN, FOIR, city tier, thin-file segment, stacking fraud rules |

**Model card:** [`ml/MODEL_CARD.md`](ml/MODEL_CARD.md) — dataset, metrics, limitations, retraining guide.

---

## Architecture

```mermaid
flowchart TB
    subgraph Client
        UI[React SPA]
    end

    subgraph Gateway
        Express[Express Gateway :5000]
    end

    subgraph API["FastAPI + PostgreSQL + Redis"]
        Auth[JWT Auth]
        Elig[Eligibility Engine]
        Risk[ML Risk + Fraud]
        Decision[Decision Engine]
        Lenders[Lender Mesh + Circuit Breaker]
        Rank[Offer Ranking]
        Admin[Admin / ML Metrics]
    end

    subgraph ML["ML Pipeline"]
        Train[train_models.py]
        Predict[predict.py + SHAP]
        Indian[Indian Synthetic Dataset]
    end

    UI --> Express
    Express -->|USE_FASTAPI=true| Auth
    Auth --> Elig --> Risk --> Decision
    Decision --> Lenders --> Rank
    Risk --> Predict
    Train --> Indian
    Train --> Predict
    Admin --> Predict
```

```text
React client (port 5000)
      │
      ▼
Express gateway (proxy when USE_FASTAPI=true)
      │
      ▼
FastAPI + PostgreSQL + Redis + Celery
      │
      ├── Eligibility engine (configurable lender policies)
      ├── Risk engine (gradient boosting via ml/predict.py)
      ├── Alternative-data thin-file score + credit-line ladder
      ├── Personalized amount / APR + consent / adverse action
      ├── Fraud engine (PAN velocity, stacking)
      ├── Decision engine (approve / review / reject)
      ├── Lender provider abstraction + circuit breaker
      ├── Offer ranking
      ├── JWT auth (register/login)
      ├── Idempotency keys
      └── Application state machine + audit events
```

OpenAPI docs: `http://localhost:8000/docs`

---

## Quick start

```bash
docker compose up -d postgres redis api worker
npm install
pip install -r backend/requirements.txt
npm run ml:indian          # generate Indian synthetic data + train model
npm run dev                # React UI + Express gateway on :5000
```

Compose starts PostgreSQL, Redis, FastAPI (`:8000`), and the worker. It does **not** serve the UI. Keep `npm run dev` running on the host for `http://localhost:5000`.

To run FastAPI on the host instead of Compose:

```bash
docker compose up -d postgres redis
npm run dev:api
npm run dev
```

Open `http://localhost:5000`

### Environment

Copy `.env.example` to `.env`. Key flags:

- `USE_FASTAPI=true` — proxy `/api` to FastAPI (recommended)
- `FASTAPI_URL=http://127.0.0.1:8000`
- `DATABASE_URL=postgresql+psycopg2://credroute:credroute@127.0.0.1:5432/credroute`

Set `USE_FASTAPI=false` to fall back to the legacy Node/MongoDB API.

**Troubleshooting:** `404` on `/api/auth/login` means the Express gateway is serving the legacy Node API. Ensure `.env` has `USE_FASTAPI=true`, restart `npm run dev`, and start FastAPI:

```bash
docker compose up -d postgres redis api
curl http://127.0.0.1:8000/api/health
```

---

## Thin-file / alternative data (Branch-shaped loop)

When CIBIL is missing or below 650, CredRoute does **not** hard-reject on the bureau PD model. It scores:

- Cash-flow (bank balance vs income, existing EMIs)
- Synthetic device/SIM tenure proxy (deterministic from PAN — **not** real SMS or contacts)
- Repeat repayment history on the PAN

A first loan is capped (₹15k–₹50k). **Simulate on-time repayment** in the result panel to raise the limit. Rejects return three borrower-facing adverse-action reasons plus a consent ledger.

Demo: use the **Thin-file gig worker** preset.

## Demo flow (2 minutes)

1. Landing page → **Apply now**
2. Submit a loan (Prime for bureau path, **Thin-file gig worker** for alt-data + starter limit)
3. Review eligibility, alt-data score, personalized amount/APR, SHAP, decision, lender mesh
4. Route to recommended lender, then **Simulate on-time repayment** to raise the credit line
5. **Admin** tab → ML metrics, applications table, drift alerts, circuit breakers

Admin credentials: `admin@credroute.demo` / `changeme123`

---

## ML pipeline

### Recommended: Indian synthetic dataset

```bash
npm run ml:indian    # 100k synthetic Indian profiles + train
```

Trains on CIBIL/income/FOIR distributions aligned with the applicant form — not the legacy US benchmark.

### Legacy US benchmark

```bash
npm run ml:train:us
```

### Metrics logged after training

ROC-AUC, **Gini**, **KS**, precision, recall, F1, accuracy — see [`ml/MODEL_CARD.md`](ml/MODEL_CARD.md).

Artifacts:
- `ml/models/credit_risk_xgb.joblib` — gradient boosting (active model)
- `ml/models/credit_risk.onnx` — logistic regression baseline
- `ml/models/metadata.json` — metrics + active model
- `ml/experiments/comparison.json` — model comparison

Risk inference fuses structured ML (85%) + FinBERT/keyword text signal (15%) + SHAP explainability.

---

## API (FastAPI)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create borrower account |
| POST | `/api/auth/login` | JWT login |
| POST | `/api/applications/evaluate` | Full pipeline: eligibility + risk + lenders + ranking |
| POST | `/api/risk/predict` | Risk score without persisting application |
| POST | `/api/applications/{id}/route` | Route to top-ranked offer |
| POST | `/api/applications/{id}/repay` | Simulate on-time repayment and raise credit line |
| GET | `/api/applications` | Recent applications (PAN masked) |
| GET | `/api/admin/ml/metrics` | Model evaluation dashboard |
| GET | `/api/metrics` | Platform metrics (cache hit rate, latency) |
| GET | `/metrics` | Prometheus scrape |
| GET | `/api/health` | Liveness + Postgres/Redis |
| GET | `/api/borrowers/{pan}/loan-history` | Warehouse loan-history join (indexed) |

---

## Tests, coverage, and proof pack

```bash
npm test
npm run test:api          # pytest (coverage if pytest-cov is installed)
npm run bench             # p50/p95, cache, fraud, decisioning, warehouse indexes
npm run bench:full        # 100k borrowers / 500k loans / 1M transactions + 100/250/500 concurrent
```

CI runs unit/integration tests, coverage, frontend build, and `bench --mode quick` on every push.

Measured numbers: [`docs/PROOF.md`](docs/PROOF.md) · last harness table: [`benchmarks/results/PROOF.md`](benchmarks/results/PROOF.md).

Locust (API up on :8000):

```bash
npm run load
```

---

## Deploy (portfolio demo)

**Option A — Railway / Render**

1. Deploy `backend/Dockerfile` as API service
2. Add PostgreSQL + Redis add-ons
3. Set env: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `CORS_ORIGINS`
4. Build frontend: `npm run build` → serve static via Express or CDN

**Option B — Docker Compose (VPS)**

```bash
docker compose up -d postgres redis api worker
npm run build && NODE_ENV=production npm start
```

`docker compose up -d` alone does not serve the React app on port 5000. Run the Express gateway (`npm start` or `npm run dev`) on the host, or put a static/nginx container in front of `client/dist`.

Add a 60–90 second Loom walkthrough link in your resume/README — recruiters often won't clone.

---

## Security notes (portfolio)

- PAN masked in API responses (`ABCXX1234X`)
- JWT auth for admin routes
- Public evaluate endpoint (intentional sandbox for demo)
- Change default admin password and `JWT_SECRET` before any public deploy

---

## What this demonstrates

- Borrower onboarding and loan application flow
- Eligibility evaluation with lender policies as data
- ML credit-risk scoring with explainability
- Fraud detection (velocity, stacking)
- Decision engine with audit trail
- Parallel mock lender integration with circuit breaker
- Offer comparison and weighted ranking
- Idempotency, PostgreSQL persistence, Redis cache
- Model monitoring and drift alerts

## Legacy stack

The original MERN implementation remains under `server/` for reference. Use `USE_FASTAPI=false` to enable it. **FastAPI is the recommended path for interviews.**
