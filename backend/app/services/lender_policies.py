"""Versioned lender policies. JSON on Lender is a copy of the active version."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.entities import Lender, LenderPolicyVersion

DRAFT = "DRAFT"
ACTIVE = "ACTIVE"
RETIRED = "RETIRED"

TYPED_FIELDS = (
    "min_income",
    "min_credit_score",
    "max_amount",
    "max_foir",
    "base_interest_rate",
    "processing_fee",
    "success_rate",
    "journey_score",
    "serves_prime",
    "serves_near_prime",
    "serves_thin_file",
    "description",
)


def policy_row_to_dict(row: LenderPolicyVersion, lender: Lender) -> dict:
    extra = dict(row.extra or {})
    return {
        "id": lender.id,
        "code": lender.code,
        "name": lender.name,
        "category": lender.category,
        "min_income": row.min_income,
        "min_credit_score": row.min_credit_score,
        "max_amount": row.max_amount,
        "max_foir": row.max_foir,
        "base_interest_rate": row.base_interest_rate,
        "processing_fee": row.processing_fee,
        "success_rate": row.success_rate,
        "journey_score": row.journey_score,
        "serves_prime": row.serves_prime,
        "serves_near_prime": row.serves_near_prime,
        "serves_thin_file": row.serves_thin_file,
        "description": row.description,
        **extra,
        "policy_version": row.version,
    }


def serialize_policy_version(row: LenderPolicyVersion) -> dict:
    return {
        "id": row.id,
        "lenderId": row.lender_id,
        "version": row.version,
        "status": row.status,
        "minIncome": row.min_income,
        "minCreditScore": row.min_credit_score,
        "maxAmount": row.max_amount,
        "maxFoir": row.max_foir,
        "baseInterestRate": row.base_interest_rate,
        "processingFee": row.processing_fee,
        "successRate": row.success_rate,
        "journeyScore": row.journey_score,
        "servesPrime": row.serves_prime,
        "servesNearPrime": row.serves_near_prime,
        "servesThinFile": row.serves_thin_file,
        "description": row.description,
        "extra": row.extra or {},
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "activatedAt": row.activated_at.isoformat() if row.activated_at else None,
    }


def active_policy(db: Session, lender: Lender) -> LenderPolicyVersion | None:
    return (
        db.query(LenderPolicyVersion)
        .filter(LenderPolicyVersion.lender_id == lender.id, LenderPolicyVersion.status == ACTIVE)
        .order_by(LenderPolicyVersion.version.desc())
        .first()
    )


def lender_to_routing_dict(db: Session, lender: Lender) -> dict:
    row = active_policy(db, lender)
    if row:
        return policy_row_to_dict(row, lender)
    return {"id": lender.id, "code": lender.code, "name": lender.name, "category": lender.category, **(lender.policy or {})}


def _next_version(db: Session, lender_id: int) -> int:
    current = (
        db.query(LenderPolicyVersion.version)
        .filter(LenderPolicyVersion.lender_id == lender_id)
        .order_by(LenderPolicyVersion.version.desc())
        .first()
    )
    return (current[0] if current else 0) + 1


def _apply_updates(row: LenderPolicyVersion, updates: dict) -> None:
    extra = dict(row.extra or {})
    for key, value in updates.items():
        if key in TYPED_FIELDS:
            setattr(row, key, value)
        else:
            extra[key] = value
    row.extra = extra or None


def create_draft(db: Session, lender: Lender, updates: dict | None = None) -> LenderPolicyVersion:
    base = active_policy(db, lender)
    row = LenderPolicyVersion(
        lender_id=lender.id,
        version=_next_version(db, lender.id),
        status=DRAFT,
        min_income=base.min_income if base else (lender.policy or {}).get("min_income"),
        min_credit_score=base.min_credit_score if base else (lender.policy or {}).get("min_credit_score"),
        max_amount=base.max_amount if base else (lender.policy or {}).get("max_amount"),
        max_foir=base.max_foir if base else (lender.policy or {}).get("max_foir"),
        base_interest_rate=base.base_interest_rate if base else (lender.policy or {}).get("base_interest_rate"),
        processing_fee=base.processing_fee if base else (lender.policy or {}).get("processing_fee"),
        success_rate=base.success_rate if base else (lender.policy or {}).get("success_rate"),
        journey_score=base.journey_score if base else (lender.policy or {}).get("journey_score"),
        serves_prime=base.serves_prime if base else bool((lender.policy or {}).get("serves_prime")),
        serves_near_prime=base.serves_near_prime if base else bool((lender.policy or {}).get("serves_near_prime")),
        serves_thin_file=base.serves_thin_file if base else bool((lender.policy or {}).get("serves_thin_file")),
        description=base.description if base else (lender.policy or {}).get("description"),
        extra=dict(base.extra) if base and base.extra else {
            key: value
            for key, value in (lender.policy or {}).items()
            if key not in TYPED_FIELDS and key not in {"id", "code", "name", "category", "policy_version"}
        },
    )
    if updates:
        _apply_updates(row, updates)
    db.add(row)
    db.flush()
    return row


def activate_policy(db: Session, lender: Lender, version: int) -> LenderPolicyVersion:
    row = (
        db.query(LenderPolicyVersion)
        .filter(LenderPolicyVersion.lender_id == lender.id, LenderPolicyVersion.version == version)
        .first()
    )
    if not row:
        raise AppError("NOT_FOUND", "Policy version not found.", 404)
    if row.min_income is None or row.max_amount is None:
        raise AppError("POLICY_INVALID", "Active policy must include min_income and max_amount.", 400)

    now = datetime.now(UTC)
    for current in db.query(LenderPolicyVersion).filter(
        LenderPolicyVersion.lender_id == lender.id,
        LenderPolicyVersion.status == ACTIVE,
    ):
        current.status = RETIRED
    row.status = ACTIVE
    row.activated_at = now
    lender.policy = policy_row_to_dict(row, lender)
    lender.policy_version = row.version
    db.flush()
    return row


def publish_policy_update(db: Session, lender: Lender, updates: dict) -> LenderPolicyVersion:
    draft = create_draft(db, lender, updates)
    return activate_policy(db, lender, draft.version)


def list_policies(db: Session, lender: Lender) -> list[LenderPolicyVersion]:
    return (
        db.query(LenderPolicyVersion)
        .filter(LenderPolicyVersion.lender_id == lender.id)
        .order_by(LenderPolicyVersion.version.desc())
        .all()
    )


def sync_seed_policy(db: Session, lender: Lender) -> LenderPolicyVersion | None:
    if active_policy(db, lender):
        return None
    draft = create_draft(db, lender)
    return activate_policy(db, lender, draft.version)
