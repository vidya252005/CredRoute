from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import AppError
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.entities import ApplicationEvent, BorrowerProfile, Lender, LoanApplication, LoanOffer, User
from app.services.application_service import serialize_application, serialize_lender_catalog
from app.services.model_monitoring import evaluate_drift, get_ml_dashboard
from app.services.underwriting_rules import load_underwriting_rules
from app.core.cache import cache_stats
from app.services.circuit_breaker import circuit_snapshot

router = APIRouter(prefix="/admin", tags=["admin"])


class LenderUpdate(BaseModel):
    active: bool | None = None
    policy: dict | None = None


@router.get("/applications")
def admin_applications(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    applications = db.query(LoanApplication).order_by(LoanApplication.created_at.desc()).limit(100).all()
    results = []
    for application in applications:
        profile = db.query(BorrowerProfile).filter(BorrowerProfile.id == application.borrower_profile_id).first()
        offers = db.query(LoanOffer).filter(LoanOffer.application_id == application.id).all()
        results.append(serialize_application(application, profile, offers))
    return results


@router.get("/metrics")
def admin_metrics(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    applications = db.query(LoanApplication).all()
    attempts = [attempt for app in applications for attempt in (app.lender_attempts or [])]
    successful = [attempt for attempt in attempts if attempt.get("status") == "success"]
    failed = [attempt for attempt in attempts if attempt.get("status") == "failed"]
    return {
        "applications": len(applications),
        "offers": db.query(LoanOffer).count(),
        "users": db.query(User).count(),
        "lenders": db.query(Lender).count(),
        "lenderSuccessRate": len(successful) / len(attempts) if attempts else 0,
        "lenderFailureRate": len(failed) / len(attempts) if attempts else 0,
        "failedLenderCalls": failed[:25],
        "circuitBreakers": circuit_snapshot(),
        "cache": cache_stats(),
    }


@router.get("/ml/metrics")
def admin_ml_metrics(_: User = Depends(require_admin)):
    return get_ml_dashboard()


@router.get("/underwriting/rules")
def admin_underwriting_rules(_: User = Depends(require_admin)):
    return load_underwriting_rules()


@router.post("/ml/drift-check")
def admin_drift_check(body: dict, _: User = Depends(require_admin)):
    from app.services.application_service import normalize_input

    input_data = normalize_input(body)
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
    _: User = Depends(require_admin),
):
    lender = db.query(Lender).filter(Lender.id == lender_id).first()
    if not lender:
        raise AppError("NOT_FOUND", "Lender not found.", 404)
    if payload.active is not None:
        lender.active = payload.active
    if payload.policy is not None:
        lender.policy = {**(lender.policy or {}), **payload.policy}
        flag_modified(lender, "policy")
    db.commit()
    return {"id": lender.id, "code": lender.code, "active": lender.active, "policy": lender.policy}
