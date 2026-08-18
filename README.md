# CredRoute

CredRoute is an experimental digital lending marketplace built with the MERN stack. A customer submits a loan request, the decision engine evaluates baseline eligibility, runs a lightweight risk model, queries fictional lender integrations in parallel, ranks the returned offers, and can route the application to the best match.

The mock lenders are intentionally fictional: `AxisBankMock`, `IDFCMock`, `LenderBMock`, and `LenderCMock`. This project does not represent or imitate the internal architecture of any real company.

## Architecture

```text
Client (React)
      │
      ▼
Express API Gateway
      │
      ├── Eligibility Engine (deterministic rules)
      ├── Risk Model (Hugging Face dataset → ONNX, default / fraud probabilities)
      ├── Lender Simulator (parallel mock integrations)
      └── Offer Ranking Engine
      │
      ├── MongoDB (users, applications, offers, events)
      └── Redis (cache, rate limiting, idempotency, BullMQ queue)
```

## Features

- Deterministic eligibility checks (age, income, employment, credit score, obligations)
- ML-inspired risk scoring trained on Hugging Face Give Me Some Credit data (ROC-AUC ~0.79)
- Parallel mock lender calls with timeout, retry, and circuit breaker
- Offer ranking: `0.35×approval + 0.25×interest + 0.20×amount_match + 0.10×success + 0.10×journey`
- Idempotency via `Idempotency-Key` header
- Redis caching for lender rules and eligibility results
- Rate limiting (20 requests/minute/IP by default)
- Application routing to the top-ranked lender
- Prometheus metrics at `/api/metrics?format=prometheus`
- BullMQ worker for async evaluation (`npm run worker`)

## Run locally

1. Copy `.env.example` to `.env`
2. Start infrastructure:

   ```bash
   docker compose up -d mongodb redis
   ```

3. Install and seed:

   ```bash
   npm install
   pip install -r ml/requirements.txt
   npm run ml:setup
   npm run seed
   npm run dev
   ```

4. Open `http://localhost:5000`

Use `npm run dev` for local development. Use `npm run start` only for production-style runs (it builds the frontend first).

### Common startup issues

| Problem | Fix |
|---------|-----|
| `ENOENT ... client/dist/index.html` | You ran production mode without a build. Use `npm run dev`, or run `npm run build` before `npm run start`. |
| `Redis is unavailable` / `ECONNREFUSED 127.0.0.1:6379` | Start Redis with `docker compose up -d redis` and set `REDIS_URL=redis://127.0.0.1:6379`, or leave `REDIS_URL` blank in `.env`. |
| Port already in use | Stop old Node processes or run `PORT=5001 npm run dev`. |

Optional observability stack:

```bash
docker compose up -d prometheus grafana
```

Grafana: `http://localhost:3000` (admin/admin)

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/lenders` | List mock lenders |
| GET | `/api/applications` | Recent applications |
| GET | `/api/metrics` | JSON metrics |
| GET | `/api/metrics?format=prometheus` | Prometheus scrape endpoint |
| POST | `/api/applications/evaluate` | Evaluate and rank offers |
| POST | `/api/applications/:id/route` | Route to best lender |

### Evaluate request

```json
{
  "name": "Aarav Mehta",
  "age": 29,
  "monthlyIncome": 65000,
  "employmentType": "salaried",
  "creditScore": 760,
  "monthlyObligations": 12000,
  "amount": 100000,
  "tenureMonths": 12
}
```

Send an `Idempotency-Key` header to prevent duplicate applications.

## ML risk model

CredRoute trains a logistic regression classifier on the Hugging Face dataset `inria-soda/tabular-benchmark` (`clf_num_credit`, Give Me Some Credit). The model predicts 90+ day delinquency probability and is exported to ONNX for inference.

```bash
pip install -r ml/requirements.txt
npm run ml:setup
```

If the model is unavailable, the API falls back to a transparent heuristic scorer.

## Tests

```bash
npm test
```

## Demo mode

If MongoDB or Redis are unavailable, the server starts in in-memory demo mode so the decision flow can still be inspected.
