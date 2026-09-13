from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import cache_stats, redis_available
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.observability import prometheus_response
from app.core.privacy import mask_pan
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.entities import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.engines.consent import ConsentService
from app.services.application_service import (
    evaluate_application,
    explain_decision,
    get_application,
    get_routing_decision,
    normalize_input,
    route_application,
    score_application,
    serialize_application,
    serialize_lender_catalog,
    simulate_repayment,
)
from app.services.profile import is_valid_pan
from app.models.entities import BorrowerProfile, LoanApplication, LoanOffer, Lender
from app.services.application_service import lender_to_dict
from app.services.circuit_breaker import circuit_snapshot

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    postgres_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        postgres_ok = False
    return {
        "ok": postgres_ok,
        "service": "credroute-fastapi",
        "postgres": postgres_ok,
        "redis": redis_available(),
    }


@router.post("/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise AppError("EMAIL_EXISTS", "An account with this email already exists.", 409)
    user = User(email=payload.email, hashed_password=hash_password(payload.password), role=UserRole.borrower)
    db.add(user)
    db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id), user.role.value))


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", 401)
    return TokenResponse(access_token=create_access_token(str(user.id), user.role.value))


@router.post("/risk/predict")
def predict_risk(body: dict, db: Session = Depends(get_db)):
    input_data = normalize_input(body)
    if not input_data["name"]:
        raise AppError("VALIDATION_ERROR", "name is required.", 400)
    if not is_valid_pan(input_data["pan"]):
        raise AppError("VALIDATION_ERROR", "pan must match format ABCDE1234F.", 400)
    ConsentService().require_alt_data(bool(input_data.get("consent_alt_data")))
    financial_notes = body.get("financialNotes") or body.get("financialText")
    scored = score_application(input_data, financial_notes, db, persist_credit_line=False)
    return {
        "eligibility": scored["eligibility"],
        "risk": scored["risk"],
        "fraud": scored["fraud"],
        "decision": scored["decision"],
        "altData": scored["altData"],
        "creditLine": scored["creditLine"],
        "personalizedOffer": scored["personalizedOffer"],
        "consent": scored["consent"],
        "adverseAction": scored["adverseAction"],
        "scoredInMs": scored["risk"].get("scoredInMs"),
    }


@router.post("/applications/evaluate")
async def evaluate(
    body: dict,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    input_data = normalize_input(body)
    if not input_data["name"]:
        raise AppError("VALIDATION_ERROR", "name is required.", 400)
    if not is_valid_pan(input_data["pan"]):
        raise AppError("VALIDATION_ERROR", "pan must match format ABCDE1234F.", 400)
    response, replay = await evaluate_application(db, body, idempotency_key)
    return {**response, "idempotentReplay": replay}


@router.post("/applications/{application_id}/route")
def route(application_id: int, db: Session = Depends(get_db)):
    try:
        return route_application(db, application_id)
    except ValueError as error:
        raise AppError("ROUTE_FAILED", str(error), 400) from error


@router.post("/applications/{application_id}/repay")
def repay(application_id: int, db: Session = Depends(get_db)):
    try:
        return simulate_repayment(db, application_id)
    except ValueError as error:
        raise AppError("REPAY_FAILED", str(error), 400) from error


@router.get("/applications/{application_id}")
def get_application_detail(application_id: int, db: Session = Depends(get_db)):
    return get_application(db, application_id)


@router.get("/applications/{application_id}/routing")
def get_application_routing(application_id: int, db: Session = Depends(get_db)):
    return get_routing_decision(db, application_id)


@router.get("/applications/{application_id}/decision/explanation")
def get_application_explanation(application_id: int, db: Session = Depends(get_db)):
    return explain_decision(db, application_id)


@router.get("/applications")
def list_applications(db: Session = Depends(get_db)):
    applications = db.query(LoanApplication).order_by(LoanApplication.created_at.desc()).limit(25).all()
    results = []
    for application in applications:
        profile = db.query(BorrowerProfile).filter(BorrowerProfile.id == application.borrower_profile_id).first()
        offers = db.query(LoanOffer).filter(LoanOffer.application_id == application.id).all()
        results.append(serialize_application(application, profile, offers))
    return results


@router.get("/lenders")
def list_lenders(db: Session = Depends(get_db)):
    lenders = db.query(Lender).filter(Lender.active.is_(True)).all()
    return [serialize_lender_catalog(lender) for lender in lenders]


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    applications = db.query(LoanApplication).all()
    attempts = [attempt for app in applications for attempt in (app.lender_attempts or [])]
    successful = [attempt for attempt in attempts if attempt.get("status") == "success"]
    latencies = [attempt.get("latencyMs", 0) for attempt in attempts if attempt.get("latencyMs")]
    return {
        "applications": len(applications),
        "offers": db.query(LoanOffer).count(),
        "lenderSuccessRate": len(successful) / len(attempts) if attempts else 0,
        "lenderFailureRate": 1 - (len(successful) / len(attempts)) if attempts else 0,
        "averageLatencyMs": round(sum(latencies) / len(latencies)) if latencies else 0,
        "cacheHitRate": cache_stats()["hitRate"],
        "cache": cache_stats(),
        "circuitBreakers": circuit_snapshot(),
        "storage": "postgresql" if "postgres" in settings.database_url else "sqlite",
    }


@router.get("/metrics/prometheus")
def metrics_prometheus():
    return prometheus_response()


@router.get("/borrowers/{pan}/loan-history")
def loan_history(pan: str, db: Session = Depends(get_db)):
    from sqlalchemy import func

    from app.models.warehouse import WarehouseBorrower, WarehouseLoan, WarehouseTransaction

    borrower = db.query(WarehouseBorrower).filter(WarehouseBorrower.pan == pan.strip().upper()).first()
    if not borrower:
        raise AppError("NOT_FOUND", "No warehouse loan history for this PAN.", 404)

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
