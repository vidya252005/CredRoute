"""Reconcile UNKNOWN lender attempts after timeouts (request may have been processed)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import LenderAttemptRecord

UNKNOWN = "unknown"
RECONCILED_FAILED = "failed"


def list_unknown_attempts(db: Session, limit: int = 50) -> list[LenderAttemptRecord]:
    return (
        db.query(LenderAttemptRecord)
        .filter(LenderAttemptRecord.status == UNKNOWN)
        .order_by(LenderAttemptRecord.id.asc())
        .limit(limit)
        .all()
    )


def reconcile_unknown_attempts(db: Session, limit: int = 50) -> dict:
    """
    Mock lenders have no external ledger. A real adapter would query the provider
    application reference and map APPROVED / REJECTED / STILL_UNKNOWN.
    """
    rows = list_unknown_attempts(db, limit)
    resolved = 0
    for row in rows:
        row.status = RECONCILED_FAILED
        row.error_code = "RECONCILED_NO_EXTERNAL_STATE"
        row.error_message = (
            row.error_message or "timeout"
        ) + "; reconciled without provider confirmation"
        resolved += 1
    if resolved:
        db.commit()
    return {"scanned": len(rows), "resolved": resolved, "stillUnknown": 0}
