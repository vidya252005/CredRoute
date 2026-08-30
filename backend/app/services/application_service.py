import hashlib
import time
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.cache import cache_get, cache_set
from app.core.exceptions import AppError
from app.core.privacy import mask_pan
from app.lenders.base import query_lenders_in_parallel
from app.models.entities import (
    ApplicationEvent,
    ApplicationStatus,
    BorrowerCreditLine,
    BorrowerProfile,
    ConsentRecord,
    IdempotencyKey,
    Lender,
    LoanApplication,
    LoanOffer,
)
from app.services.alt_data import score_alt_data
from app.services.compliance import adverse_action, build_consent
from app.services.credit_line import (
    get_or_create_credit_line,
    record_on_time_repayment,
    record_origination,
    serialize_line,
    starter_limit,
    stepped_limit,
)
from app.services.decision_engine import evaluate_decision
from app.services.eligibility import evaluate_eligibility
from app.services.fraud import evaluate_fraud
from app.services.model_monitoring import evaluate_drift
from app.services.offer_pricing import price_offer
from app.services.offer_ranking import rank_offers
from app.services.profile import classify_profile
from app.services.risk import calculate_risk
from app.services.state_machine import assert_transition

STATUS_MAP = {
    "ineligible": ApplicationStatus.ineligible,
    "rejected": ApplicationStatus.rejected,
    "under_review": ApplicationStatus.under_review,
    "offers_ready": ApplicationStatus.offers_ready,
}


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
            "pan": mask_pan(profile.pan),
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
        "lenderAttempts": application.lender_attempts or [],
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


def _require_int(body: dict, field: str, fallback: int | None = None) -> int:
    if field not in body or body[field] in ("", None):
        if fallback is not None:
            return fallback
        raise AppError("VALIDATION_ERROR", f"{field} is required.", 400)
    try:
        return int(body[field])
    except (TypeError, ValueError) as exc:
        raise AppError("VALIDATION_ERROR", f"{field} must be an integer.", 400) from exc


def normalize_input(body: dict) -> dict:
    pan = (body.get("pan") or "").strip().upper()
    cibil = body.get("cibilScore")
    if cibil in ("", None, 0):
        cibil = None
    else:
        try:
            cibil = int(cibil)
        except (TypeError, ValueError) as exc:
            raise AppError("VALIDATION_ERROR", "cibilScore must be an integer.", 400) from exc
        if cibil <= 0:
            cibil = None
    try:
        existing_emis = int(body.get("existingEmis") or body.get("monthlyObligations") or 0)
        bank_balance = int(body.get("bankStatementAvgBalance") or 0)
        city_tier = int(body.get("cityTier") or 1)
    except (TypeError, ValueError) as exc:
        raise AppError(
            "VALIDATION_ERROR",
            "existingEmis, bankStatementAvgBalance, and cityTier must be integers.",
            400,
        ) from exc
    return {
        "name": str(body.get("name", "")).strip(),
        "pan": pan,
        "age": _require_int(body, "age"),
        "monthly_income": _require_int(body, "monthlyIncome"),
        "income_type": str(body.get("incomeType") or ""),
        "cibil_score": cibil,
        "existing_emis": existing_emis,
        "bank_statement_avg_balance": bank_balance,
        "city_tier": city_tier,
        "amount": _require_int(body, "amount"),
        "tenure_months": _require_int(body, "tenureMonths"),
        "consent_alt_data": body.get("consentAltData") is True,
        "android_api_level": body.get("androidApiLevel"),
        "sim_tenure_months": body.get("simTenureMonths"),
        "rooted": body.get("rooted"),
    }


def score_application(
    input_data: dict,
    financial_notes: str | None,
    db: Session,
    persist_credit_line: bool = True,
) -> dict:
    started = time.perf_counter()
    profile = classify_profile(input_data)
    device_overrides = {
        "androidApiLevel": input_data.get("android_api_level"),
        "simTenureMonths": input_data.get("sim_tenure_months"),
        "rooted": input_data.get("rooted"),
    }

    notes_token = hashlib.sha256((financial_notes or "").encode("utf-8")).hexdigest()[:16]
    cache_key = (
        f"risk:{input_data['pan']}:{input_data['amount']}:{input_data['tenure_months']}:"
        f"{input_data['monthly_income']}:{input_data.get('cibil_score')}:"
        f"{input_data['existing_emis']}:{input_data['income_type']}:"
        f"{input_data.get('bank_statement_avg_balance')}:{input_data.get('city_tier')}:"
        f"{notes_token}"
    )
    cached = cache_get(cache_key)
    if cached:
        risk = cached
    else:
        risk = calculate_risk(input_data, financial_notes)
        cache_set(cache_key, risk, 120)

    existing_line = (
        db.query(BorrowerCreditLine).filter(BorrowerCreditLine.pan == input_data["pan"]).first()
        if db is not None
        else None
    )
    credit_preview = (
        serialize_line(existing_line)
        if existing_line
        else {"firstLoan": True, "onTimeRepayments": 0, "currentLimit": 0, "nextLimit": 0, "originatedCount": 0}
    )
    alt_data = score_alt_data(input_data, credit_preview, device_overrides)

    if persist_credit_line and db is not None:
        line = get_or_create_credit_line(
            db, input_data["pan"], input_data["monthly_income"], alt_data["altDataScore"]
        )
        if line.originated_count == 0:
            line.current_limit = starter_limit(input_data["monthly_income"], alt_data["altDataScore"])
            line.starter_limit = line.current_limit
            line.next_limit = stepped_limit(line.starter_limit, 1, input_data["monthly_income"])
        credit = serialize_line(line)
    elif existing_line:
        credit = serialize_line(existing_line)
    else:
        base = starter_limit(input_data["monthly_income"], alt_data["altDataScore"])
        credit = {
            "firstLoan": True,
            "currentLimit": base,
            "nextLimit": stepped_limit(base, 1, input_data["monthly_income"]),
            "onTimeRepayments": 0,
            "originatedCount": 0,
        }

    priced = price_offer(input_data, risk, alt_data, credit, profile["segment"])
    priced_input = {
        **input_data,
        "amount": priced["offeredAmount"],
        "tenure_months": priced["tenureMonths"],
    }
    eligibility = evaluate_eligibility(
        input_data,
        offered_amount=priced["offeredAmount"],
        offered_tenure=priced["tenureMonths"],
    )
    fraud = evaluate_fraud(db, priced_input, risk)
    risk = {
        **risk,
        "fraud": fraud,
        "fraudProbability": fraud["fraudProbability"],
        "drift": evaluate_drift(input_data),
        "altData": alt_data,
        "creditLine": credit,
        "personalizedOffer": priced,
    }
    decision = evaluate_decision(eligibility, risk, fraud, alt_data)
    consent = build_consent(input_data, alt_data, bool(input_data.get("consent_alt_data")))
    action = adverse_action(decision, eligibility, alt_data, fraud)
    scored_ms = round((time.perf_counter() - started) * 1000)
    priced["scoredInMs"] = scored_ms
    decision["adverseAction"] = action
    risk.update(
        {
            "decision": decision,
            "consent": consent,
            "adverseAction": action,
            "scoredInMs": scored_ms,
            "personalizedOffer": priced,
        }
    )
    return {
        "eligibility": eligibility,
        "risk": risk,
        "fraud": fraud,
        "decision": decision,
        "altData": alt_data,
        "creditLine": credit,
        "personalizedOffer": priced,
        "consent": consent,
        "adverseAction": action,
        "pricedInput": priced_input,
    }


async def evaluate_application(db: Session, body: dict, idempotency_key: str | None) -> tuple[dict, bool]:
    if idempotency_key:
        cached = db.query(IdempotencyKey).filter(IdempotencyKey.key == idempotency_key).first()
        if cached:
            return cached.response, True

    input_data = normalize_input(body)
    if not input_data["consent_alt_data"]:
        raise AppError(
            "CONSENT_REQUIRED",
            "Consent is required to use cash-flow and device-proxy signals for underwriting.",
            400,
        )

    financial_notes = body.get("financialNotes") or body.get("financialText")
    scored = score_application(input_data, financial_notes, db)
    eligibility = scored["eligibility"]
    risk = scored["risk"]
    fraud = scored["fraud"]
    decision = scored["decision"]
    profile = eligibility["profile"]
    priced_input = scored["pricedInput"]

    offers = []
    attempts = []
    if decision["decision"] in ("approve", "review"):
        lenders = [lender_to_dict(item) for item in db.query(Lender).filter(Lender.active.is_(True)).all()]
        attempts = await query_lenders_in_parallel(lenders, priced_input, risk, profile)
        raw_offers = [attempt["offer"] for attempt in attempts if attempt.get("status") == "success"]
        offers = rank_offers(raw_offers, priced_input, profile)
        for offer in offers:
            offer["maxAmount"] = min(offer.get("maxAmount", priced_input["amount"]), priced_input["amount"])

        if not offers and scored["altData"].get("thinFileEligible"):
            thin_lenders = [
                item for item in lenders if item.get("serves_thin_file") or item.get("servesThinFile")
            ]
            originator = thin_lenders[0] if thin_lenders else None
            if originator:
                priced = scored["personalizedOffer"]
                offers = [
                    {
                        "lenderId": originator["id"],
                        "lenderCode": originator["code"],
                        "lenderName": originator["name"],
                        "interestRate": priced["apr"],
                        "processingFee": originator.get("processing_fee", originator.get("processingFee", 0)),
                        "approvalProbability": 0.72,
                        "maxAmount": priced["offeredAmount"],
                        "rank": 1,
                        "score": 1.0,
                        "monthlyPayment": priced["monthlyPayment"],
                        "routingReason": (
                            "Starter ticket originated on alternative data after bureau-path lenders declined"
                        ),
                    }
                ]

    profile_row = BorrowerProfile(
        name=input_data["name"],
        pan=input_data["pan"],
        age=input_data["age"],
        income_type=input_data["income_type"],
        monthly_income=input_data["monthly_income"],
        cibil_score=input_data["cibil_score"],
        existing_emis=input_data["existing_emis"],
        bank_statement_avg_balance=input_data["bank_statement_avg_balance"],
        city_tier=input_data["city_tier"],
    )
    db.add(profile_row)
    db.flush()

    status = STATUS_MAP.get(decision["status"], ApplicationStatus.ineligible)
    adverse = scored["adverseAction"]
    if decision["decision"] in ("approve", "review") and not offers:
        decision = {
            "decision": "reject",
            "status": "ineligible",
            "reasons": ["No lender offers available for this profile and ticket size"],
            "explainability": decision.get("explainability"),
        }
        adverse = adverse_action(decision, eligibility, scored["altData"], fraud)
        decision["adverseAction"] = adverse
        risk["decision"] = decision
        risk["adverseAction"] = adverse
        status = ApplicationStatus.ineligible

    application = LoanApplication(
        borrower_profile_id=profile_row.id,
        amount=priced_input["amount"],
        tenure_months=priced_input["tenure_months"],
        status=status,
        eligibility=eligibility,
        risk=risk,
        lender_attempts=[{k: v for k, v in attempt.items() if k != "offer"} for attempt in attempts],
        idempotency_key=idempotency_key,
    )
    db.add(application)
    db.flush()

    db.add(
        ConsentRecord(
            application_id=application.id,
            pan=input_data["pan"],
            granted=True,
            payload=scored["consent"],
        )
    )

    offer_rows = []
    for offer in offers:
        row = LoanOffer(
            application_id=application.id,
            lender_id=offer["lenderId"],
            lender_code=offer["lenderCode"],
            lender_name=offer["lenderName"],
            interest_rate=offer["interestRate"],
            processing_fee=offer["processingFee"],
            approval_probability=offer["approvalProbability"],
            max_amount=offer["maxAmount"],
            rank=offer["rank"],
            score=offer["score"],
            monthly_payment=offer["monthlyPayment"],
            routing_reason=offer.get("routingReason"),
        )
        db.add(row)
        offer_rows.append(row)
    db.flush()

    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="consent_recorded",
            event_metadata={"purposes": [item["id"] for item in scored["consent"]["purposes"]]},
        )
    )
    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="risk_scored",
            event_metadata={
                "defaultProbability": risk.get("defaultProbability"),
                "fraudProbability": fraud.get("fraudProbability"),
                "riskBand": risk.get("riskBand"),
                "altDataScore": scored["altData"].get("altDataScore"),
                "scoredInMs": risk.get("scoredInMs"),
                "driftAlert": risk.get("drift", {}).get("driftAlert"),
            },
        )
    )
    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="decision_made",
            event_metadata={"decision": decision.get("decision"), "reasons": decision.get("reasons", [])},
        )
    )
    if adverse:
        db.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="adverse_action",
                event_metadata=adverse,
            )
        )
    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="application_evaluated",
            event_metadata={
                "segment": profile.get("segment"),
                "offerCount": len(offers),
                "offeredAmount": priced_input["amount"],
            },
        )
    )

    response = serialize_application(application, profile_row, offer_rows)
    if idempotency_key:
        db.add(IdempotencyKey(key=idempotency_key, response=response))
    db.commit()
    from app.core.observability import record_decision
    from app.services.events import publish_decision_pipeline

    record_decision(decision.get("decision"))
    publish_decision_pipeline(application.id, decision, risk)
    return response, False


def route_application(db: Session, application_id: int) -> dict:
    application = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not application:
        raise ValueError("Application not found.")
    if application.status == ApplicationStatus.routed:
        offers = db.query(LoanOffer).filter(LoanOffer.application_id == application.id).all()
        profile = db.query(BorrowerProfile).filter(BorrowerProfile.id == application.borrower_profile_id).first()
        return {"application": serialize_application(application, profile, offers), "alreadyRouted": True}

    offers = db.query(LoanOffer).filter(LoanOffer.application_id == application.id).order_by(LoanOffer.rank).all()
    recommended = next((offer for offer in offers if offer.rank == 1), None)
    if not recommended:
        raise ValueError("No ranked offer available to route.")

    assert_transition(application.status, ApplicationStatus.routed)
    application.status = ApplicationStatus.routed
    application.routed_lender_code = recommended.lender_code
    application.selected_offer_id = recommended.id

    profile = db.query(BorrowerProfile).filter(BorrowerProfile.id == application.borrower_profile_id).first()
    line = db.query(BorrowerCreditLine).filter(BorrowerCreditLine.pan == profile.pan).first()
    if line:
        record_origination(line, application.amount)
        risk = dict(application.risk or {})
        risk["creditLine"] = serialize_line(line)
        application.risk = risk
        flag_modified(application, "risk")

    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="application_routed",
            event_metadata={"lenderCode": recommended.lender_code, "lenderName": recommended.lender_name},
        )
    )
    db.commit()
    serialized = serialize_application(application, profile, offers)
    return {"application": serialized, "alreadyRouted": False, "routedOffer": serialized["offers"][0] if serialized["offers"] else None}


def simulate_repayment(db: Session, application_id: int) -> dict:
    application = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not application:
        raise ValueError("Application not found.")
    if application.status != ApplicationStatus.routed:
        raise ValueError("Repayment can only be simulated after the application is routed.")

    profile = db.query(BorrowerProfile).filter(BorrowerProfile.id == application.borrower_profile_id).first()
    line = db.query(BorrowerCreditLine).filter(BorrowerCreditLine.pan == profile.pan).first()
    if not line:
        raise ValueError("No credit line found for this borrower.")

    credit = record_on_time_repayment(line, profile.monthly_income)
    risk = dict(application.risk or {})
    risk["creditLine"] = credit
    if risk.get("personalizedOffer"):
        risk["personalizedOffer"] = {**risk["personalizedOffer"], "nextLimit": credit["nextLimit"], "currentLimit": credit["currentLimit"]}
    application.risk = risk
    flag_modified(application, "risk")
    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="repayment_recorded",
            event_metadata={"onTimeRepayments": credit["onTimeRepayments"], "newLimit": credit["currentLimit"]},
        )
    )
    db.commit()
    offers = db.query(LoanOffer).filter(LoanOffer.application_id == application.id).all()
    return {"application": serialize_application(application, profile, offers), "creditLine": credit}
