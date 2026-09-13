from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import AppError
from app.core.privacy import mask_pan
from app.models.entities import (
    ApplicationEvent,
    ApplicationStatus,
    BorrowerCreditLine,
    BorrowerProfile,
    ConsentRecord,
    DecisionAudit,
    Lender,
    LoanApplication,
    LoanOffer,
    RoutingDecision,
)
from app.domain.context import DecisionContext
from app.engines.consent import ConsentService
from app.engines.decision import DecisionEngine
from app.routing.engine import RoutingEngine
from app.services.audit import persist_decision_audit
from app.services.compliance import adverse_action
from app.services.credit_line import record_on_time_repayment, record_origination, serialize_line
from app.services.idempotency import IdempotencyService
from app.services.state_machine import ApplicationStateMachine

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
    context = DecisionContext.from_input(input_data, financial_notes)
    return DecisionEngine().evaluate(context, db, persist_credit_line=persist_credit_line)


async def evaluate_application(db: Session, body: dict, idempotency_key: str | None) -> tuple[dict, bool]:
    idempotency = IdempotencyService(db)
    cached, digest = idempotency.lookup(idempotency_key, body)
    if cached is not None:
        return cached, True

    input_data = normalize_input(body)
    ConsentService().require_alt_data(bool(input_data.get("consent_alt_data")))

    financial_notes = body.get("financialNotes") or body.get("financialText")
    scored = score_application(input_data, financial_notes, db)
    eligibility = scored["eligibility"]
    risk = scored["risk"]
    fraud = scored["fraud"]
    decision = scored["decision"]
    profile = eligibility["profile"]
    priced_input = scored["pricedInput"]
    context = scored.get("context") or DecisionContext.from_input(input_data, financial_notes)

    offers = []
    attempts = []
    routing = None
    if decision["decision"] in ("approve", "review"):
        routing = await RoutingEngine().route(db, context, scored)
        offers = [offer.to_dict() for offer in routing.offers]
        attempts = routing.attempts

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
        scored["decision"] = decision
        scored["adverseAction"] = adverse

    application = LoanApplication(
        borrower_profile_id=profile_row.id,
        amount=priced_input["amount"],
        tenure_months=priced_input["tenure_months"],
        status=status,
        eligibility=eligibility,
        risk=risk,
        lender_attempts=attempts,
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
                "routingStrategy": routing.routing_strategy if routing else None,
            },
        )
    )
    persist_decision_audit(db, application.id, context, scored, routing)

    response = serialize_application(application, profile_row, offer_rows)
    idempotency.store(idempotency_key, digest, response)
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

    ApplicationStateMachine().transition(application, ApplicationStatus.routed)
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


def load_application_bundle(db: Session, application_id: int) -> tuple[LoanApplication, BorrowerProfile, list[LoanOffer]]:
    application = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not application:
        raise AppError("NOT_FOUND", "Application not found.", 404)
    profile = db.query(BorrowerProfile).filter(BorrowerProfile.id == application.borrower_profile_id).first()
    offers = db.query(LoanOffer).filter(LoanOffer.application_id == application.id).all()
    return application, profile, offers


def get_application(db: Session, application_id: int) -> dict:
    application, profile, offers = load_application_bundle(db, application_id)
    return serialize_application(application, profile, offers)


def get_routing_decision(db: Session, application_id: int) -> dict:
    application, _profile, offers = load_application_bundle(db, application_id)
    ranked = sorted(offers, key=lambda item: item.rank)
    selected = next((offer for offer in ranked if offer.rank == 1), None)
    routing_row = (
        db.query(RoutingDecision)
        .filter(RoutingDecision.application_id == application.id)
        .order_by(RoutingDecision.id.desc())
        .first()
    )
    attempts = application.lender_attempts or []
    return {
        "applicationId": application.id,
        "status": "COMPLETED" if ranked or application.status in {ApplicationStatus.ineligible, ApplicationStatus.rejected} else "PENDING",
        "selectedLender": application.routed_lender_code or (selected.lender_code if selected else None),
        "selectedOfferId": application.selected_offer_id or (selected.id if selected else None),
        "strategy": routing_row.strategy if routing_row else "balanced",
        "strategyVersion": routing_row.strategy_version if routing_row else None,
        "policyVersion": routing_row.policy_version if routing_row else None,
        "candidates": [
            {
                "lenderCode": attempt.get("lenderCode"),
                "status": attempt.get("status"),
                "eligible": attempt.get("status") == "success",
                "latencyMs": attempt.get("latencyMs"),
                "message": attempt.get("message"),
            }
            for attempt in attempts
        ],
        "offers": [
            {
                "id": offer.id,
                "lenderCode": offer.lender_code,
                "score": offer.score,
                "rank": offer.rank,
                "interestRate": offer.interest_rate,
                "approvalProbability": offer.approval_probability,
                "routingReason": offer.routing_reason,
            }
            for offer in ranked
        ],
    }


def explain_decision(db: Session, application_id: int) -> dict:
    application, _profile, offers = load_application_bundle(db, application_id)
    risk = application.risk or {}
    decision = risk.get("decision") or {}
    audit = (
        db.query(DecisionAudit)
        .filter(DecisionAudit.application_id == application.id)
        .order_by(DecisionAudit.id.desc())
        .first()
    )
    ranked = sorted(offers, key=lambda item: item.rank)
    selected = next((offer for offer in ranked if offer.rank == 1), None)
    lender_explanations = []
    for attempt in application.lender_attempts or []:
        offer = next((item for item in ranked if item.lender_code == attempt.get("lenderCode")), None)
        reasons = []
        if attempt.get("message"):
            reasons.append(attempt["message"])
        if offer and offer.routing_reason:
            reasons.append(offer.routing_reason)
        lender_explanations.append(
            {
                "lenderCode": attempt.get("lenderCode"),
                "eligible": attempt.get("status") == "success",
                "rejectionReasons": reasons if attempt.get("status") != "success" else [],
                "score": offer.score if offer else None,
                "latencyMs": attempt.get("latencyMs"),
                "status": attempt.get("status"),
            }
        )
    final_reasons = list(decision.get("reasons") or [])
    if selected:
        final_reasons = final_reasons + [
            f"Eligible for requested amount",
            selected.routing_reason or "Highest weighted offer score",
        ]
    return {
        "applicationId": application.id,
        "decision": decision.get("decision"),
        "status": application.status.value if hasattr(application.status, "value") else str(application.status),
        "reasons": final_reasons,
        "explainability": decision.get("explainability") or (audit.explainability if audit else {}),
        "risk": {
            "band": risk.get("riskBand"),
            "defaultProbability": risk.get("defaultProbability"),
        },
        "selectedLender": selected.lender_code if selected else None,
        "lenders": lender_explanations,
        "modelVersion": audit.model_version if audit else risk.get("modelSource"),
        "policyVersion": audit.policy_version if audit else None,
        "routingVersion": audit.routing_version if audit else None,
        "featureSnapshot": audit.feature_snapshot if audit else None,
    }
