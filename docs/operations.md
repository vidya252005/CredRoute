# Operations

| Probe | Meaning |
|-------|---------|
| `GET /api/health/live` | Process up |
| `GET /api/health/ready` | Postgres reachable (Redis reported) |
| `GET /api/metrics` | SQL aggregates, cache, circuit snapshot |
| `GET /metrics` | Prometheus |

Circuit breaker state is Redis-backed when Redis is up, otherwise process-local.

Idempotency keys: `IN_PROGRESS` → `COMPLETED` / `FAILED`, 24h TTL.

Reconcile timed-out lender calls:

```text
POST /api/admin/reconciliation/run
```

or Celery task `app.workers.tasks.reconcile_unknown_attempts`.
