"""Operational metrics from SQL aggregates — never load the applications table."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import cache_stats
from app.models.entities import Lender, LenderAttemptRecord, LoanApplication, LoanOffer, User
from app.services.circuit_breaker import circuit_snapshot


def platform_metrics(db: Session) -> dict:
    applications = db.query(func.count(LoanApplication.id)).scalar() or 0
    offers = db.query(func.count(LoanOffer.id)).scalar() or 0
    attempt_count = db.query(func.count(LenderAttemptRecord.id)).scalar() or 0
    success_count = (
        db.query(func.count(LenderAttemptRecord.id))
        .filter(LenderAttemptRecord.status == "success")
        .scalar()
        or 0
    )
    avg_latency = (
        db.query(func.avg(LenderAttemptRecord.latency_ms))
        .filter(LenderAttemptRecord.latency_ms.isnot(None))
        .scalar()
    )
    return {
        "applications": int(applications),
        "offers": int(offers),
        "lenderSuccessRate": (success_count / attempt_count) if attempt_count else 0,
        "lenderFailureRate": (1 - (success_count / attempt_count)) if attempt_count else 0,
        "averageLatencyMs": round(float(avg_latency)) if avg_latency is not None else 0,
        "cacheHitRate": cache_stats()["hitRate"],
        "cache": cache_stats(),
        "circuitBreakers": circuit_snapshot(),
    }


def admin_metrics(db: Session) -> dict:
    base = platform_metrics(db)
    unknown_count = (
        db.query(func.count(LenderAttemptRecord.id))
        .filter(LenderAttemptRecord.status == "unknown")
        .scalar()
        or 0
    )
    failed = (
        db.query(LenderAttemptRecord)
        .filter(LenderAttemptRecord.status.in_(("failed", "unknown")))
        .order_by(LenderAttemptRecord.id.desc())
        .limit(25)
        .all()
    )
    return {
        **base,
        "users": db.query(func.count(User.id)).scalar() or 0,
        "lenders": db.query(func.count(Lender.id)).scalar() or 0,
        "unknownLenderCalls": int(unknown_count),
        "failedLenderCalls": [
            {
                "lenderCode": row.lender_code,
                "status": row.status,
                "latencyMs": row.latency_ms,
                "message": row.error_message,
            }
            for row in failed
        ],
    }
