from fastapi import APIRouter, Depends, Header
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.evaluate_application import EvaluateApplicationUseCase
from app.application.get_application import GetApplicationUseCase
from app.application.route_application import RouteApplicationUseCase
from app.application.simulate_repayment import SimulateRepaymentUseCase
from app.core.cache import redis_available
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.core.observability import prometheus_response
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.engines.consent import ConsentService
from app.models.entities import Lender, User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.application_service import (
    normalize_input,
    score_application,
    serialize_lender_catalog,
)
from app.services.metrics_query import platform_metrics

router = APIRouter()


@router.get("/health/live")
def liveness():
    return {"ok": True, "status": "live"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    postgres_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        postgres_ok = False
    redis_ok = redis_available()
    ready = postgres_ok
    return {
        "ok": ready,
        "status": "ready" if ready else "not_ready",
        "postgres": postgres_ok,
        "redis": redis_ok,
    }


@router.get("/health")
def health(db: Session = Depends(get_db)):
    body = readiness(db)
    return {
        "ok": body["ok"],
        "service": "credroute-fastapi",
        "postgres": body["postgres"],
        "redis": body["redis"],
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
    user: User | None = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    response, replay = await EvaluateApplicationUseCase(db).execute(
        body,
        idempotency_key,
        user.id if user else None,
    )
    return {**response, "idempotentReplay": replay}


@router.post("/applications/{application_id}/route")
def route(
    application_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    try:
        return RouteApplicationUseCase(db).execute(application_id, user)
    except ValueError as error:
        raise AppError("ROUTE_FAILED", str(error), 400) from error


@router.post("/applications/{application_id}/repay")
def repay(
    application_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    try:
        return SimulateRepaymentUseCase(db).execute(application_id, user)
    except ValueError as error:
        raise AppError("REPAY_FAILED", str(error), 400) from error


@router.get("/applications/{application_id}")
def get_application_detail(
    application_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return GetApplicationUseCase(db).get(application_id, user)


@router.get("/applications/{application_id}/routing")
def get_application_routing(
    application_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return GetApplicationUseCase(db).routing(application_id, user)


@router.get("/applications/{application_id}/decision/explanation")
def get_application_explanation(
    application_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return GetApplicationUseCase(db).explanation(application_id, user)


@router.get("/applications")
def list_applications(db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    return GetApplicationUseCase(db).list_visible(user)


@router.get("/lenders")
def list_lenders(db: Session = Depends(get_db)):
    lenders = db.query(Lender).filter(Lender.active.is_(True)).all()
    return [serialize_lender_catalog(lender) for lender in lenders]


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    return {
        **platform_metrics(db),
        "storage": "postgresql" if "postgres" in settings.database_url else "sqlite",
    }


@router.get("/metrics/prometheus")
def metrics_prometheus():
    return prometheus_response()
