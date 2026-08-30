#!/usr/bin/env python3
"""CredRoute proof harness: latency, cache, fraud, decisioning, warehouse indexes."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

warnings.filterwarnings("ignore", message="X does not have valid feature names")
warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`")

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmarks" / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


def _pct(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((percentile / 100) * (len(ordered) - 1)))))
    return round(ordered[index], 3)


def _summary(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "meanMs": round(statistics.mean(values), 3),
        "p50Ms": _pct(values, 50),
        "p95Ms": _pct(values, 95),
        "p99Ms": _pct(values, 99),
        "maxMs": round(max(values), 3),
    }


def _prime(i: int = 0) -> dict:
    letter = chr(65 + (i % 26))
    return {
        "name": "Proof Applicant",
        "pan": f"ABCDE{i % 10000:04d}{letter}",
        "age": 29,
        "monthly_income": 85000,
        "income_type": "salaried",
        "cibil_score": 780,
        "existing_emis": 12000,
        "bank_statement_avg_balance": 90000,
        "city_tier": 1,
        "amount": 300000,
        "tenure_months": 24,
        "consent_alt_data": True,
    }


def bench_inference(repeats: int) -> dict:
    os.environ["CREDROUTE_ML_SUBPROCESS"] = "1"
    from app.services import risk as risk_mod

    risk_mod._ml_module = None
    risk_mod._ml_failed = False
    payload = _prime()
    risk_mod.predict_with_model(payload)
    cold = []
    for _ in range(max(3, repeats // 8)):
        started = time.perf_counter()
        risk_mod.predict_with_model(payload)
        cold.append((time.perf_counter() - started) * 1000)
    subprocess_stats = _summary(cold)

    os.environ.pop("CREDROUTE_ML_SUBPROCESS", None)
    risk_mod._ml_module = None
    risk_mod._ml_failed = False
    risk_mod.predict_with_model(payload)
    warm = []
    for _ in range(repeats):
        started = time.perf_counter()
        risk_mod.predict_with_model(payload)
        warm.append((time.perf_counter() - started) * 1000)
    inprocess_stats = _summary(warm)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: risk_mod.predict_with_model(_prime()), range(min(32, repeats))))
    concurrent_ms = (time.perf_counter() - started) * 1000
    n = min(32, repeats)
    return {
        "subprocess": subprocess_stats,
        "inprocess": inprocess_stats,
        "concurrentPredictions": n,
        "concurrentTotalMs": round(concurrent_ms, 3),
        "predictionsPerSecond": round(n / (concurrent_ms / 1000), 2) if concurrent_ms else None,
        "latencyReductionPct": (
            round(100 * (1 - inprocess_stats["p95Ms"] / subprocess_stats["p95Ms"]), 1)
            if subprocess_stats.get("p95Ms") and inprocess_stats.get("p95Ms")
            else None
        ),
    }


def bench_decisioning(n: int) -> dict:
    from app.services.application_service import score_application

    counts = {"approve": 0, "review": 0, "reject": 0}
    explained = 0
    latencies = []
    for i in range(n):
        body = _prime(i)
        if i % 7 == 0:
            body.update({"cibil_score": None, "monthly_income": 28000, "income_type": "gig", "amount": 80000})
        if i % 11 == 0:
            body.update({"existing_emis": 60000, "cibil_score": 610, "age": 22})
        started = time.perf_counter()
        scored = score_application(body, None, None, persist_credit_line=False)
        latencies.append((time.perf_counter() - started) * 1000)
        decision = scored["decision"]["decision"]
        counts[decision] = counts.get(decision, 0) + 1
        risk = scored["risk"]
        if risk.get("shapFactors") or risk.get("riskFactors"):
            explained += 1
    automated = counts["approve"] + counts["reject"]
    return {
        "applications": n,
        "decisions": counts,
        "automatedDecisionRate": round(automated / n, 4) if n else 0,
        "explainedRate": round(explained / n, 4) if n else 0,
        "latency": _summary(latencies),
    }


def bench_fraud() -> dict:
    from app.services.fraud import score_fraud_signals

    cases = []
    for _ in range(40):
        cases.append(({"age": 29, "monthly_income": 85000, "existing_emis": 8000, "amount": 200000, "cibil_score": 780, "rooted": False}, 0, 0))
    for _ in range(15):
        cases.append(({"age": 22, "monthly_income": 20000, "existing_emis": 14000, "amount": 500000, "cibil_score": 520, "rooted": True}, 6, 1))
    for _ in range(15):
        cases.append(({"age": 35, "monthly_income": 40000, "existing_emis": 25000, "amount": 900000, "cibil_score": 600, "rooted": False}, 22, 1))

    threshold = 0.25
    tp = fp = tn = fn = 0
    for body, recent, label in cases:
        result = score_fraud_signals(body, {"fraudProbability": 0.05}, recent)
        pred = 1 if result["blocked"] or result["fraudProbability"] >= threshold else 0
        if pred == 1 and label == 1:
            tp += 1
        elif pred == 1 and label == 0:
            fp += 1
        elif pred == 0 and label == 0:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    return {
        "threshold": threshold,
        "samples": len(cases),
        "truePositives": tp,
        "falsePositives": fp,
        "trueNegatives": tn,
        "falseNegatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "falsePositiveRate": round(fp / (fp + tn), 4) if fp + tn else 0,
        "falseNegativeRate": round(fn / (fn + tp), 4) if fn + tp else 0,
        "detectedFraudRate": round(tp / (tp + fn), 4) if tp + fn else 0,
    }


def bench_cache() -> dict:
    from app.core.cache import cache_delete, cache_get, cache_set, cache_stats, redis_available, reset_cache_client

    reset_cache_client()
    key = "proof:feature:prime"
    payload = {"defaultProbability": 0.08}
    uncached = []
    for _ in range(20):
        cache_delete(key)
        started = time.perf_counter()
        cache_get(key)
        cache_set(key, payload, 30)
        uncached.append((time.perf_counter() - started) * 1000)
    cached = []
    for _ in range(40):
        started = time.perf_counter()
        cache_get(key)
        cached.append((time.perf_counter() - started) * 1000)
    stats = cache_stats()
    uncached_p95 = _pct(uncached, 95) or 1
    cached_p95 = _pct(cached, 95) or 1
    reduction = None
    if redis_available() and uncached_p95 >= 0.05:
        reduction = round(100 * (1 - cached_p95 / uncached_p95), 1)
    return {
        "redisAvailable": redis_available(),
        "stats": stats,
        "uncached": _summary(uncached),
        "cached": _summary(cached),
        "latencyReductionPct": reduction,
    }


def _warehouse_bind(mode: str):
    from sqlalchemy import create_engine, text

    from app.db.session import engine as app_engine

    try:
        with app_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return app_engine, False
    except Exception as exc:
        if mode == "full":
            raise RuntimeError(
                "Postgres is not reachable. Start it with "
                "`docker compose up -d postgres redis` then retry `npm run bench:full`."
            ) from exc
        sqlite_path = RESULTS / "proof-warehouse.db"
        print(
            f"[proof] Postgres is not reachable ({exc}); using sqlite {sqlite_path} for quick mode.",
            file=sys.stderr,
        )
        return create_engine(
            f"sqlite:///{sqlite_path}",
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        ), True


def bench_warehouse(mode: str) -> dict:
    from sqlalchemy import text

    from app.services.scale_data import (
        HISTORY_SQL,
        analyze_warehouse,
        create_warehouse_indexes,
        drop_warehouse_indexes,
        generate_scale_data,
        pan_for,
    )

    bind, sqlite_fallback = _warehouse_bind(mode)
    loaded = generate_scale_data(mode, bind=bind)
    pans = [pan_for(i) for i in range(min(25, loaded["borrowers"]))]

    def timed(label: str) -> dict:
        samples = []
        with bind.connect() as conn:
            for pan in pans:
                started = time.perf_counter()
                conn.execute(text(HISTORY_SQL), {"pan": pan}).fetchall()
                samples.append((time.perf_counter() - started) * 1000)
        return {"label": label, **_summary(samples)}

    drop_warehouse_indexes(bind)
    before = timed("before_index")
    create_warehouse_indexes(bind)
    analyze_warehouse(bind)
    after = timed("after_index")
    reduction = None
    if before.get("p95Ms") and after.get("p95Ms"):
        reduction = round(100 * (1 - after["p95Ms"] / before["p95Ms"]), 1)
    backend = "sqlite-fallback" if sqlite_fallback else loaded.get("dialect")
    return {
        "dataset": loaded,
        "before": before,
        "after": after,
        "latencyReductionPct": reduction,
        "backend": backend,
    }


def bench_api(requests_n: int, concurrency: int) -> dict:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    latencies = []
    errors = 0
    timeouts = 0

    def once(i: int):
        started = time.perf_counter()
        try:
            response = client.get("/api/health")
            elapsed = (time.perf_counter() - started) * 1000
            return elapsed, response.status_code >= 400, False
        except Exception:
            return (time.perf_counter() - started) * 1000, True, True

    started_all = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(once, i) for i in range(requests_n)]
        for future in as_completed(futures):
            elapsed, error, timeout = future.result()
            latencies.append(elapsed)
            errors += int(error)
            timeouts += int(timeout)
    wall = time.perf_counter() - started_all
    return {
        "requests": requests_n,
        "concurrency": concurrency,
        "errorRate": round(errors / requests_n, 4) if requests_n else 0,
        "timeoutRate": round(timeouts / requests_n, 4) if requests_n else 0,
        "requestsPerSecond": round(requests_n / wall, 2) if wall else None,
        "latency": _summary(latencies),
    }


def load_ml_metadata() -> dict:
    path = ROOT / "ml" / "models" / "metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_int(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value}{suffix}"


def _section_error(block: dict | None) -> str | None:
    if not isinstance(block, dict):
        return None
    error = block.get("error")
    return str(error) if error else None


def write_proof(payload: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "PROOF.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    ml = payload.get("ml", {})
    models = ml.get("models") or {}
    baseline = models.get("baseline_logistic_regression") or {}
    boost = models.get("gradient_boosting") or models.get("xgboost") or {}
    inf = payload.get("inference") or {}
    dec = payload.get("decisioning") or {}
    fraud = payload.get("fraud") or {}
    cache = payload.get("cache") or {}
    db = payload.get("database") or {}
    api = payload.get("api") or {}
    dataset = db.get("dataset") or {}

    warehouse_cell = _section_error(db)
    if not warehouse_cell:
        warehouse_cell = (
            f"{_fmt_int(dataset.get('borrowers'))} borrowers · "
            f"{_fmt_int(dataset.get('loans'))} loans · "
            f"{_fmt_int(dataset.get('transactions'))} transactions"
        )
        if db.get("backend"):
            warehouse_cell += f" ({db['backend']})"

    index_cell = _section_error(db)
    if not index_cell:
        index_cell = (
            f"Loan-history p95 reduced **{_fmt(db.get('latencyReductionPct'), '%')}** "
            f"({_fmt((db.get('before') or {}).get('p95Ms'))} → {_fmt((db.get('after') or {}).get('p95Ms'))} ms)"
        )

    api_cell = _section_error(api) or (
        f"{_fmt(api.get('concurrency'))} concurrent · {_fmt(api.get('requestsPerSecond'))} rps · "
        f"p50/p95 {_fmt((api.get('latency') or {}).get('p50Ms'))} / {_fmt((api.get('latency') or {}).get('p95Ms'))} ms"
    )
    inf_cell = _section_error(inf) or (
        f"In-process p95 {_fmt((inf.get('inprocess') or {}).get('p95Ms'))} ms vs subprocess "
        f"{_fmt((inf.get('subprocess') or {}).get('p95Ms'))} ms (**{_fmt(inf.get('latencyReductionPct'), '%')}** faster)"
    )
    cache_cell = _section_error(cache) or (
        f"Hit rate **{round((((cache.get('stats') or {}).get('hitRate')) or 0) * 100, 1)}%** · "
        f"retrieval {_fmt(cache.get('latencyReductionPct'), '%')} faster when warm"
    )
    fraud_cell = _section_error(fraud) or (
        f"Detected **{round((fraud.get('detectedFraudRate') or 0) * 100, 1)}%** of labeled fraud "
        f"at FPR {round((fraud.get('falsePositiveRate') or 0) * 100, 1)}%"
    )
    dec_cell = _section_error(dec) or (
        f"Automated decision rate **{round((dec.get('automatedDecisionRate') or 0) * 100, 1)}%** "
        f"of {_fmt(dec.get('applications'))} simulated applications"
    )

    md = f"""# CredRoute proof pack

Generated `{payload.get("generatedAt")}`. Mode: **{payload.get("mode")}**.

## Non-negotiable checklist

| Item | Proof |
|------|-------|
| Credit-risk engine | `{ml.get("activeModel")}` · ROC-AUC baseline {baseline.get("rocAuc")} → GBM {boost.get("rocAuc")} |
| Approve / Review / Reject | {dec_cell} |
| Synthetic warehouse | {warehouse_cell} |
| API load | {api_cell} |
| PostgreSQL indexes | {index_cell} |
| ML metrics | Precision {boost.get("precision")} · Recall {boost.get("recall")} · F1 {boost.get("f1")} |
| Fraud | {fraud_cell} |
| Redis cache | {cache_cell} |
| Explainability | **{round((dec.get("explainedRate") or 0)*100, 1)}%** of decisions include SHAP/risk factors |
| Inference | {inf_cell} |

## Reproduce

```bash
docker compose up -d postgres redis
PYTHONPATH=backend python3 backend/benchmarks/run_proof.py --mode quick
PYTHONPATH=backend python3 backend/benchmarks/run_proof.py --mode full   # 100k / 500k / 1M
```
"""
    (RESULTS / "PROOF.md").write_text(md, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    args = parser.parse_args()
    inference_n = 16 if args.mode == "quick" else 40
    decision_n = 40 if args.mode == "quick" else 200
    api_n = 80 if args.mode == "quick" else 250
    api_c = 20 if args.mode == "quick" else 100

    def _safe(label, fn):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            print(f"[proof] {label} failed: {exc}", file=sys.stderr)
            return {"error": f"{label}: {exc}"}

    payload = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "mode": args.mode,
        "ml": load_ml_metadata(),
        "inference": _safe("inference", lambda: bench_inference(inference_n)),
        "decisioning": _safe("decisioning", lambda: bench_decisioning(decision_n)),
        "fraud": _safe("fraud", bench_fraud),
        "cache": _safe("cache", bench_cache),
        "database": _safe("database", lambda: bench_warehouse(args.mode)),
        "api": _safe("api", lambda: bench_api(api_n, api_c)),
    }
    if args.mode == "full":
        payload["apiScale"] = {
            "c100": _safe("api100", lambda: bench_api(200, 100)),
            "c250": _safe("api250", lambda: bench_api(250, 250)),
            "c500": _safe("api500", lambda: bench_api(400, 500)),
        }
    write_proof(payload)
    print(json.dumps(payload, indent=2, default=str))
    print(f"Wrote {RESULTS / 'PROOF.md'}")


if __name__ == "__main__":
    main()
