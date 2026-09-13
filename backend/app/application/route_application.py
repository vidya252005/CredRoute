from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import require_application_access
from app.core.exceptions import AppError
from app.models.entities import ApplicationEvent, ApplicationStatus, User
from app.services.application_service import load_application_bundle, locked_credit_line, serialize_application
from app.services.credit_line import record_origination, serialize_line
from app.services.state_machine import ApplicationStateMachine


class RouteApplicationUseCase:
    def __init__(self, db: Session):
        self.db = db

    def execute(self, application_id: int, user: User | None = None) -> dict:
        application, profile, offers = load_application_bundle(self.db, application_id)
        require_application_access(user, profile)
        if application.status == ApplicationStatus.routed:
            return {"application": serialize_application(application, profile, offers), "alreadyRouted": True}

        ranked = sorted(offers, key=lambda item: item.rank)
        recommended = next((offer for offer in ranked if offer.rank == 1), None)
        if not recommended:
            raise AppError("ROUTE_FAILED", "No ranked offer available to route.", 400)

        ApplicationStateMachine().transition(application, ApplicationStatus.routed)
        application.routed_lender_code = recommended.lender_code
        application.selected_offer_id = recommended.id

        line = locked_credit_line(self.db, profile)
        if line:
            record_origination(line, application.amount)
            risk = dict(application.risk or {})
            risk["creditLine"] = serialize_line(line)
            application.risk = risk
            flag_modified(application, "risk")

        self.db.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="application_routed",
                event_metadata={"lenderCode": recommended.lender_code, "lenderName": recommended.lender_name},
            )
        )
        self.db.commit()
        serialized = serialize_application(application, profile, ranked)
        return {
            "application": serialized,
            "alreadyRouted": False,
            "routedOffer": serialized["offers"][0] if serialized["offers"] else None,
        }
