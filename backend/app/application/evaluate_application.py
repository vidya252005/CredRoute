from sqlalchemy.orm import Session

from app.core.identity import SensitiveIdentity
from app.core.observability import record_decision
from app.core.request_context import current_request_id
from app.domain.context import DecisionContext
from app.engines.consent import ConsentService
from app.models.entities import (
    ApplicationEvent,
    ApplicationStatus,
    BorrowerProfile,
    ConsentRecord,
    LenderAttemptRecord,
    LoanApplication,
    LoanOffer,
)
from app.routing.engine import RoutingEngine
from app.services.application_service import (
    normalize_input,
    redact_pii,
    score_application,
    serialize_application,
)
from app.services.audit import persist_decision_audit
from app.services.compliance import adverse_action
from app.services.idempotency import IdempotencyService
from app.services.outbox import publish_pending_outbox, queue_decision_events

STATUS_MAP = {
    "ineligible": ApplicationStatus.ineligible,
    "rejected": ApplicationStatus.rejected,
    "under_review": ApplicationStatus.under_review,
    "offers_ready": ApplicationStatus.offers_ready,
}


class EvaluateApplicationUseCase:
    def __init__(self, db: Session):
        self.db = db

    async def execute(
        self,
        body: dict,
        idempotency_key: str | None,
        user_id: int | None = None,
    ) -> tuple[dict, bool]:
        input_data = normalize_input(body)
        ConsentService().require_alt_data(bool(input_data.get("consent_alt_data")))
        identity = SensitiveIdentity(input_data["pan"])
        idempotency = IdempotencyService(self.db)
        action, digest, cached = idempotency.claim(idempotency_key, body)
        if action == "replay":
            return cached or {}, True
        if idempotency_key:
            self.db.commit()

        try:
            return await self._process(body, input_data, identity, user_id, idempotency, idempotency_key, digest)
        except Exception:
            self.db.rollback()
            idempotency.fail(idempotency_key)
            self.db.commit()
            raise

    async def _process(
        self,
        body: dict,
        input_data: dict,
        identity: SensitiveIdentity,
        user_id: int | None,
        idempotency: IdempotencyService,
        idempotency_key: str | None,
        digest: str | None,
    ) -> tuple[dict, bool]:
        db = self.db
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
        routing = None
        if decision["decision"] in ("approve", "review"):
            routing = await RoutingEngine().route(db, context, scored)
            offers = [offer.to_dict() for offer in routing.offers]

        profile_row = BorrowerProfile(
            user_id=user_id,
            name=input_data["name"],
            pan=identity.pan_masked,
            pan_hash=identity.pan_hash,
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
            eligibility=redact_pii(eligibility),
            risk=redact_pii(risk),
            lender_attempts=None,
            idempotency_key=idempotency_key,
        )
        db.add(application)
        db.flush()

        db.add(
            ConsentRecord(
                application_id=application.id,
                pan=identity.pan_masked,
                pan_hash=identity.pan_hash,
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

        request_id = current_request_id()
        db.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="consent_recorded",
                event_metadata={"purposes": [item["id"] for item in scored["consent"]["purposes"]], "requestId": request_id},
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
                    "requestId": request_id,
                },
            )
        )
        db.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="decision_made",
                event_metadata={"decision": decision.get("decision"), "reasons": decision.get("reasons", []), "requestId": request_id},
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
                    "requestId": request_id,
                },
            )
        )
        persist_decision_audit(db, application.id, context, scored, routing)
        queue_decision_events(db, application.id, decision, risk)
        db.flush()
        application.attempt_records = (
            db.query(LenderAttemptRecord).filter(LenderAttemptRecord.application_id == application.id).all()
        )

        response = serialize_application(application, profile_row, offer_rows)
        idempotency.complete(idempotency_key, digest, response)
        db.commit()
        record_decision(decision.get("decision"))
        publish_pending_outbox(db)
        return response, False


async def evaluate_application(
    db: Session,
    body: dict,
    idempotency_key: str | None,
    user_id: int | None = None,
) -> tuple[dict, bool]:
    return await EvaluateApplicationUseCase(db).execute(body, idempotency_key, user_id)
