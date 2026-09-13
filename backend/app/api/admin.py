from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import require_admin
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.entities import ApplicationEvent, Lender, LoanApplication, User
from app.schemas.application import EvaluateApplicationRequest, LenderPolicyUpdateRequest
from app.services.application_service import serialize_application, serialize_lender_catalog
from app.services.lender_policies import (
    activate_policy,
    create_draft,
    list_policies,
    publish_policy_update,
    serialize_policy_version,
)
from app.services.metrics_query import admin_metrics as query_admin_metrics
from app.services.reconciliation import list_unknown_attempts, reconcile_unknown_attempts
from app.services.model_monitoring import evaluate_drift, get_ml_dashboard
from app.services.underwriting_rules import load_underwriting_rules

router = APIRouter(prefix="/admin", tags=["admin"])


class LenderUpdate(BaseModel):
    active: bool | None = None
    policy: LenderPolicyUpdateRequest | None = None


@router.get("/applications")
def admin_applications(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    applications = (
        db.query(LoanApplication)
        .options(
            selectinload(LoanApplication.borrower_profile),
            selectinload(LoanApplication.offers),
            selectinload(LoanApplication.attempt_records),
        )
        .order_by(LoanApplication.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        serialize_application(application, application.borrower_profile, list(application.offers or []))
        for application in applications
    ]


@router.get("/metrics")
def admin_metrics(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return query_admin_metrics(db)


@router.get("/ml/metrics")
def admin_ml_metrics(_: User = Depends(require_admin)):
    return get_ml_dashboard()


@router.get("/underwriting/rules")
@router.get("/underwriting/rules/active")
def admin_underwriting_rules(_: User = Depends(require_admin)):
    return load_underwriting_rules()


@router.get("/underwriting/rules/versions")
def admin_underwriting_rule_versions(_: User = Depends(require_admin)):
    rules = load_underwriting_rules()
    return {"active": rules.get("version"), "versions": [rules.get("version")]}


@router.post("/ml/drift-check")
def admin_drift_check(body: EvaluateApplicationRequest, _: User = Depends(require_admin)):
    from app.services.application_service import normalize_input

    input_data = normalize_input(body.model_dump())
    return evaluate_drift(input_data)


@router.get("/events")
def admin_events(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    events = db.query(ApplicationEvent).order_by(ApplicationEvent.created_at.desc()).limit(50).all()
    return [
        {
            "id": event.id,
            "applicationId": event.application_id,
            "eventType": event.event_type,
            "metadata": event.event_metadata,
            "createdAt": event.created_at.isoformat() if event.created_at else None,
        }
        for event in events
    ]


@router.get("/lenders")
def admin_lenders(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    lenders = db.query(Lender).order_by(Lender.id).all()
    return [serialize_lender_catalog(lender) for lender in lenders]


@router.patch("/lenders/{lender_id}")
def update_lender(
    lender_id: int,
    payload: LenderUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    lender = db.query(Lender).filter(Lender.id == lender_id).first()
    if not lender:
        raise AppError("NOT_FOUND", "Lender not found.", 404)
    if payload.active is not None:
        lender.active = payload.active
    if payload.policy is not None:
        updates = payload.policy.model_dump(exclude_none=True)
        if updates:
            publish_policy_update(db, lender, updates)
            flag_modified(lender, "policy")
    db.commit()
    return {
        "id": lender.id,
        "code": lender.code,
        "active": lender.active,
        "policy": lender.policy,
        "policyVersion": lender.policy_version,
        "updatedBy": admin.email,
    }


@router.get("/lenders/{lender_id}/policies")
def admin_lender_policies(lender_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    lender = db.query(Lender).filter(Lender.id == lender_id).first()
    if not lender:
        raise AppError("NOT_FOUND", "Lender not found.", 404)
    return [serialize_policy_version(row) for row in list_policies(db, lender)]


@router.post("/lenders/{lender_id}/policies/draft")
def admin_create_policy_draft(
    lender_id: int,
    payload: LenderPolicyUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    lender = db.query(Lender).filter(Lender.id == lender_id).first()
    if not lender:
        raise AppError("NOT_FOUND", "Lender not found.", 404)
    row = create_draft(db, lender, payload.model_dump(exclude_none=True))
    db.commit()
    return serialize_policy_version(row)


@router.post("/lenders/{lender_id}/policies/{version}/activate")
def admin_activate_policy(
    lender_id: int,
    version: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    lender = db.query(Lender).filter(Lender.id == lender_id).first()
    if not lender:
        raise AppError("NOT_FOUND", "Lender not found.", 404)
    row = activate_policy(db, lender, version)
    db.commit()
    return serialize_policy_version(row)


@router.get("/reconciliation/unknown")
def admin_unknown_attempts(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [
        {
            "id": row.id,
            "applicationId": row.application_id,
            "lenderCode": row.lender_code,
            "status": row.status,
            "latencyMs": row.latency_ms,
            "message": row.error_message,
        }
        for row in list_unknown_attempts(db)
    ]


@router.post("/reconciliation/run")
def admin_run_reconciliation(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return reconcile_unknown_attempts(db)


@router.get("/borrowers/{borrower_id}/loan-history")
def admin_loan_history(borrower_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    from sqlalchemy import func

    from app.core.privacy import mask_pan
    from app.models.warehouse import WarehouseBorrower, WarehouseLoan, WarehouseTransaction

    borrower = db.query(WarehouseBorrower).filter(WarehouseBorrower.id == borrower_id).first()
    if not borrower:
        raise AppError("NOT_FOUND", "No warehouse loan history for this borrower.", 404)

    loan_count = (
        db.query(func.count(WarehouseLoan.id)).filter(WarehouseLoan.borrower_id == borrower.id).scalar() or 0
    )
    loan_volume = (
        db.query(func.coalesce(func.sum(WarehouseLoan.amount), 0))
        .filter(WarehouseLoan.borrower_id == borrower.id)
        .scalar()
        or 0
    )
    txn_count = (
        db.query(func.count(WarehouseTransaction.id))
        .filter(WarehouseTransaction.borrower_id == borrower.id)
        .scalar()
        or 0
    )
    bounces = (
        db.query(func.count(WarehouseTransaction.id))
        .filter(
            WarehouseTransaction.borrower_id == borrower.id,
            WarehouseTransaction.txn_type == "bounce",
        )
        .scalar()
        or 0
    )
    recent = (
        db.query(WarehouseLoan)
        .filter(WarehouseLoan.borrower_id == borrower.id)
        .order_by(WarehouseLoan.originated_at.desc())
        .limit(10)
        .all()
    )
    return {
        "pan": mask_pan(borrower.pan),
        "borrowerId": borrower.id,
        "loanCount": int(loan_count),
        "loanVolume": int(loan_volume),
        "transactionCount": int(txn_count),
        "bounceCount": int(bounces),
        "recentLoans": [
            {
                "id": loan.id,
                "amount": loan.amount,
                "status": loan.status,
                "originatedAt": loan.originated_at.isoformat() if loan.originated_at else None,
            }
            for loan in recent
        ],
    }
