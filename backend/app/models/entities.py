import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UserRole(str, enum.Enum):
    borrower = "borrower"
    admin = "admin"


class ApplicationStatus(str, enum.Enum):
    draft = "DRAFT"
    submitted = "SUBMITTED"
    under_review = "UNDER_REVIEW"
    eligible = "ELIGIBLE"
    offers_ready = "OFFERS_READY"
    ineligible = "INELIGIBLE"
    offer_selected = "OFFER_SELECTED"
    routed = "ROUTED"
    approved = "APPROVED"
    rejected = "REJECTED"
    expired = "EXPIRED"
    failed = "FAILED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.borrower)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BorrowerProfile(Base):
    __tablename__ = "borrower_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    pan: Mapped[str] = mapped_column(String(10), index=True)
    age: Mapped[int] = mapped_column(Integer)
    income_type: Mapped[str] = mapped_column(String(32))
    monthly_income: Mapped[int] = mapped_column(Integer)
    cibil_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    existing_emis: Mapped[int] = mapped_column(Integer, default=0)
    bank_statement_avg_balance: Mapped[int] = mapped_column(Integer, default=0)
    city_tier: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Lender(Base):
    __tablename__ = "lenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    policy: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    borrower_profile_id: Mapped[int] = mapped_column(ForeignKey("borrower_profiles.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    tenure_months: Mapped[int] = mapped_column(Integer)
    status: Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus), default=ApplicationStatus.offers_ready, index=True)
    eligibility: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lender_attempts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    routed_lender_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selected_offer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    offers: Mapped[list["LoanOffer"]] = relationship(back_populates="application")


class LoanOffer(Base):
    __tablename__ = "loan_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    lender_id: Mapped[int] = mapped_column(ForeignKey("lenders.id"))
    lender_code: Mapped[str] = mapped_column(String(64))
    lender_name: Mapped[str] = mapped_column(String(120))
    interest_rate: Mapped[float] = mapped_column(Float)
    processing_fee: Mapped[int] = mapped_column(Integer)
    approval_probability: Mapped[float] = mapped_column(Float)
    max_amount: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    monthly_payment: Mapped[int] = mapped_column(Integer)
    routing_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped[LoanApplication] = relationship(back_populates="offers")


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BorrowerCreditLine(Base):
    __tablename__ = "borrower_credit_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pan: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    current_limit: Mapped[int] = mapped_column(Integer)
    next_limit: Mapped[int] = mapped_column(Integer)
    starter_limit: Mapped[int] = mapped_column(Integer)
    on_time_repayments: Mapped[int] = mapped_column(Integer, default=0)
    originated_count: Mapped[int] = mapped_column(Integer, default=0)
    last_originated_amount: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    pan: Mapped[str] = mapped_column(String(10), index=True)
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    default_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_band: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FraudAssessment(Base):
    __tablename__ = "fraud_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    fraud_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionAudit(Base):
    __tablename__ = "decision_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    routing_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    feature_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lender_results: Mapped[list | None] = mapped_column(JSON, nullable=True)
    final_decision: Mapped[str] = mapped_column(String(32))
    reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    explainability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LenderAttemptRecord(Base):
    __tablename__ = "lender_attempt_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    lender_code: Mapped[str] = mapped_column(String(64), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoutingDecision(Base):
    __tablename__ = "routing_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), index=True)
    selected_offer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_lender: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strategy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoutingCandidate(Base):
    __tablename__ = "routing_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("routing_decisions.id"), index=True)
    lender_code: Mapped[str] = mapped_column(String(64))
    eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rejection_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)

