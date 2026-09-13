from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.core.identity import is_valid_pan
from app.core.privacy import mask_pan
from app.schemas.application import EvaluateApplicationRequest
from app.models.entities import (
    BorrowerCreditLine,
    BorrowerProfile,
    Lender,
    LoanApplication,
    LoanOffer,
)
from app.domain.context import DecisionContext
from app.engines.decision import DecisionEngine


def lender_to_dict(lender: Lender) -> dict:
    policy = lender.policy or {}
    return {"id": lender.id, "code": lender.code, "name": lender.name, "category": lender.category, **policy}


def serialize_lender_catalog(lender: Lender) -> dict:
    policy = lender.policy or {}
    return {
        "id": str(lender.id),
        "code": lender.code,
        "name": lender.name,
        "category": lender.category,
        "description": policy.get("description"),
        "minIncome": policy.get("min_income"),
        "minCreditScore": policy.get("min_credit_score"),
        "maxAmount": policy.get("max_amount"),
        "maxFoir": policy.get("max_foir"),
        "baseInterestRate": policy.get("base_interest_rate"),
        "processingFee": policy.get("processing_fee"),
        "successRate": policy.get("success_rate"),
        "journeyScore": policy.get("journey_score"),
        "servesPrime": policy.get("serves_prime"),
        "servesNearPrime": policy.get("serves_near_prime"),
        "servesThinFile": policy.get("serves_thin_file"),
        "active": lender.active,
        "policyVersion": lender.policy_version,
    }


def serialize_application(application: LoanApplication, profile: BorrowerProfile, offers: list[LoanOffer]) -> dict:
    risk = application.risk or {}
    return {
        "id": str(application.id),
        "createdAt": application.created_at.isoformat() if application.created_at else None,
        "amount": application.amount,
        "tenureMonths": application.tenure_months,
        "status": application.status.name.lower(),
        "routedLenderCode": application.routed_lender_code,
        "decision": risk.get("decision"),
        "applicant": {
            "name": profile.name,
            "pan": profile.pan,
            "age": profile.age,
            "monthlyIncome": profile.monthly_income,
            "incomeType": profile.income_type,
            "cibilScore": profile.cibil_score,
            "existingEmis": profile.existing_emis,
            "bankStatementAvgBalance": profile.bank_statement_avg_balance,
            "cityTier": profile.city_tier,
        },
        "eligibility": application.eligibility,
        "risk": risk,
        "fraud": risk.get("fraud"),
        "altData": risk.get("altData"),
        "creditLine": risk.get("creditLine"),
        "personalizedOffer": risk.get("personalizedOffer"),
        "consent": risk.get("consent"),
        "adverseAction": risk.get("adverseAction"),
        "scoredInMs": risk.get("scoredInMs"),
        "lenderAttempts": _serialize_attempts(application),
        "offers": [
            {
                "id": str(offer.id),
                "lenderCode": offer.lender_code,
                "lenderName": offer.lender_name,
                "interestRate": offer.interest_rate,
                "processingFee": offer.processing_fee,
                "approvalProbability": offer.approval_probability,
                "maxAmount": offer.max_amount,
                "rank": offer.rank,
                "score": offer.score,
                "monthlyPayment": offer.monthly_payment,
                "routingReason": offer.routing_reason,
            }
            for offer in sorted(offers, key=lambda item: item.rank)
        ],
    }


def _serialize_attempts(application: LoanApplication) -> list[dict]:
    records = getattr(application, "attempt_records", None) or []
    if records:
        return [
            {
                "status": row.status,
                "lenderCode": row.lender_code,
                "latencyMs": row.latency_ms,
                "message": row.error_message,
            }
            for row in records
        ]
    return application.lender_attempts or []


def redact_pii(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if str(key).lower() in {"pan", "permanent_account_number"}:
                redacted[key] = mask_pan(item) if isinstance(item, str) else item
            else:
                redacted[key] = redact_pii(item)
        return redacted
    if isinstance(value, list):
        return [redact_pii(item) for item in value]
    if isinstance(value, str) and is_valid_pan(value):
        return mask_pan(value)
    return value


def normalize_input(body: dict) -> dict:
    try:
        payload = EvaluateApplicationRequest.model_validate(body)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = first.get("loc", ("field",))[-1]
        raise AppError("VALIDATION_ERROR", f"{loc}: {first.get('msg', 'invalid value')}", 400) from exc
    return {
        "name": payload.name.strip(),
        "pan": payload.pan,
        "age": payload.age,
        "monthly_income": payload.monthlyIncome,
        "income_type": payload.incomeType,
        "cibil_score": payload.cibilScore,
        "existing_emis": payload.existingEmis,
        "bank_statement_avg_balance": payload.bankStatementAvgBalance,
        "city_tier": payload.cityTier,
        "amount": payload.amount,
        "tenure_months": payload.tenureMonths,
        "consent_alt_data": payload.consentAltData is True,
        "android_api_level": payload.androidApiLevel,
        "sim_tenure_months": payload.simTenureMonths,
        "rooted": payload.rooted,
    }


def score_application(
    input_data: dict,
    financial_notes: str | None,
    db: Session,
    persist_credit_line: bool = True,
) -> dict:
    context = DecisionContext.from_input(input_data, financial_notes)
    return DecisionEngine().evaluate(context, db, persist_credit_line=persist_credit_line)


def locked_credit_line(db: Session, profile: BorrowerProfile | None) -> BorrowerCreditLine | None:
    if not profile or not profile.pan_hash:
        return None
    return (
        db.query(BorrowerCreditLine)
        .filter(BorrowerCreditLine.pan_hash == profile.pan_hash)
        .with_for_update()
        .first()
    )


def load_application_bundle(db: Session, application_id: int) -> tuple[LoanApplication, BorrowerProfile, list[LoanOffer]]:
    application = (
        db.query(LoanApplication)
        .options(
            selectinload(LoanApplication.borrower_profile),
            selectinload(LoanApplication.offers),
            selectinload(LoanApplication.attempt_records),
        )
        .filter(LoanApplication.id == application_id)
        .first()
    )
    if not application:
        raise AppError("NOT_FOUND", "Application not found.", 404)
    return application, application.borrower_profile, list(application.offers or [])
