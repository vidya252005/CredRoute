# CredRoute

**Digital lending decisioning + mock lender routing** for Indian retail credit workflows.

A production-**inspired** portfolio system. Synthetic data and mock lenders only — not a regulated lending platform.

> Mock lenders · Synthetic data · No real banks, NBFCs, or credit bureaus.

## What it solves

Borrowers submit a loan ticket. CredRoute scores eligibility and risk, applies fraud and thin-file rules, then queries mock lenders in parallel and ranks offers.

Interesting engineering (not more features): typed use cases, versioned lender policies, race-safe idempotency, transactional outbox, PAN hashing, owner-scoped APIs, UNKNOWN provider timeouts + reconciliation.

```text
React (:5000) → Express gateway → FastAPI
                                    ├─ EvaluateApplication
                                    ├─ DecisionEngine → Risk / Fraud / Alt-data / Policy
                                    └─ RoutingEngine → adapters → rank → Postgres + outbox
```

OpenAPI: `http://localhost:8000/docs`  
Deeper notes: [`docs/architecture.md`](docs/architecture.md) · [decisioning](docs/decision-engine.md) · [routing](docs/routing.md) · [ML](docs/ml.md) · [security](docs/security.md) · [ops](docs/operations.md)

## Demo

```bash
cp .env.example .env          # set JWT/PAN/admin locally; do not commit secrets
docker compose up -d postgres redis api
npm install
pip install -r backend/requirements.txt
npm run ml:indian             # optional: train the synthetic model
npm run dev                   # UI + gateway on :5000
```

1. **Apply now** — Prime or Thin-file gig worker preset  
2. Review decision, offers, SHAP  
3. Route, then simulate on-time repayment  
4. Admin tab needs `ADMIN_EMAIL` + `ADMIN_PASSWORD` in `.env`

## Performance & testing

```bash
npm test
npm run test:api
npm run bench                 # see docs/PROOF.md — include hardware when you republish numbers
```

CI: unit/integration tests, coverage, frontend build, quick bench.

**Model metrics are indicative only** (synthetic data, not real bureau populations). Model card: [`ml/MODEL_CARD.md`](ml/MODEL_CARD.md).

## Limitations

- Mock lenders, not HTTP provider contracts in production
- Public evaluate is a demo sandbox; owned apps are authorized
- Celery is post-processing (reconciliation), not the evaluate path
- Legacy MERN under `server/` is history only — FastAPI is the application
