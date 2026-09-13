from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import require_application_access
from app.core.exceptions import AppError
from app.models.entities import ApplicationEvent, ApplicationStatus, User
from app.services.application_service import load_application_bundle, locked_credit_line, serialize_application
from app.services.credit_line import record_on_time_repayment


class SimulateRepaymentUseCase:
    def __init__(self, db: Session):
        self.db = db

    def execute(self, application_id: int, user: User | None = None) -> dict:
        application, profile, offers = load_application_bundle(self.db, application_id)
        require_application_access(user, profile)
        if application.status != ApplicationStatus.routed:
            raise AppError("REPAY_FAILED", "Repayment can only be simulated after the application is routed.", 400)

        line = locked_credit_line(self.db, profile)
        if not line:
            raise AppError("REPAY_FAILED", "No credit line found for this borrower.", 400)

        credit = record_on_time_repayment(line, profile.monthly_income)
        risk = dict(application.risk or {})
        risk["creditLine"] = credit
        if risk.get("personalizedOffer"):
            risk["personalizedOffer"] = {
                **risk["personalizedOffer"],
                "nextLimit": credit["nextLimit"],
                "currentLimit": credit["currentLimit"],
            }
        application.risk = risk
        flag_modified(application, "risk")
        self.db.add(
            ApplicationEvent(
                application_id=application.id,
                event_type="repayment_recorded",
                event_metadata={"onTimeRepayments": credit["onTimeRepayments"], "newLimit": credit["currentLimit"]},
            )
        )
        self.db.commit()
        return {"application": serialize_application(application, profile, offers), "creditLine": credit}
