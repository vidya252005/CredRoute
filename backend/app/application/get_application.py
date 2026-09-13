from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_application_access
from app.models.entities import (
    ApplicationStatus,
    BorrowerProfile,
    DecisionAudit,
    LoanApplication,
    RoutingDecision,
    User,
    UserRole,
)
from app.services.application_service import (
    _serialize_attempts,
    load_application_bundle,
    serialize_application,
)


class GetApplicationUseCase:
    def __init__(self, db: Session):
        self.db = db

    def get(self, application_id: int, user: User | None = None) -> dict:
        application, profile, offers = load_application_bundle(self.db, application_id)
        require_application_access(user, profile)
        return serialize_application(application, profile, offers)

    def routing(self, application_id: int, user: User | None = None) -> dict:
        application, profile, offers = load_application_bundle(self.db, application_id)
        require_application_access(user, profile)
        ranked = sorted(offers, key=lambda item: item.rank)
        selected = next((offer for offer in ranked if offer.rank == 1), None)
        routing_row = (
            self.db.query(RoutingDecision)
            .filter(RoutingDecision.application_id == application.id)
            .order_by(RoutingDecision.id.desc())
            .first()
        )
        attempts = _serialize_attempts(application)
        return {
            "applicationId": application.id,
            "status": (
                "COMPLETED"
                if ranked or application.status in {ApplicationStatus.ineligible, ApplicationStatus.rejected}
                else "PENDING"
            ),
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

    def explanation(self, application_id: int, user: User | None = None) -> dict:
        application, profile, offers = load_application_bundle(self.db, application_id)
        require_application_access(user, profile)
        risk = application.risk or {}
        decision = risk.get("decision") or {}
        audit = (
            self.db.query(DecisionAudit)
            .filter(DecisionAudit.application_id == application.id)
            .order_by(DecisionAudit.id.desc())
            .first()
        )
        ranked = sorted(offers, key=lambda item: item.rank)
        selected = next((offer for offer in ranked if offer.rank == 1), None)
        lender_explanations = []
        for attempt in _serialize_attempts(application):
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
                "Eligible for requested amount",
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

    def list_visible(self, user: User | None) -> list[dict]:
        if user is None:
            return []
        query = (
            self.db.query(LoanApplication)
            .options(
                selectinload(LoanApplication.borrower_profile),
                selectinload(LoanApplication.offers),
                selectinload(LoanApplication.attempt_records),
            )
            .order_by(LoanApplication.created_at.desc())
        )
        if user.role != UserRole.admin:
            query = query.join(BorrowerProfile).filter(BorrowerProfile.user_id == user.id)
        applications = query.limit(100 if user.role == UserRole.admin else 25).all()
        return [
            serialize_application(application, application.borrower_profile, list(application.offers or []))
            for application in applications
        ]
