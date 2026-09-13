# Architecture

CredRoute is a **monolith**: React client → Express gateway → FastAPI → PostgreSQL + Redis.

```text
API
 └─ EvaluateApplication / RouteApplication / SimulateRepayment / GetApplication
      └─ DecisionEngine (orchestrates risk, fraud, alt-data, affordability, policy)
           └─ RoutingEngine
                └─ Candidate filter → concurrent lender adapters → rank → RoutingDecision
                     └─ same DB transaction: application, audit, outbox
```

Celery is **post-processing only** (outbox-adjacent jobs, UNKNOWN attempt reconciliation). Evaluate is synchronous so the demo can return offers in one request.

See also: [decision-engine.md](decision-engine.md), [routing.md](routing.md), [security.md](security.md), [operations.md](operations.md).
