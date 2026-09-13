from app.models.entities import ApplicationStatus

ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.draft: {ApplicationStatus.submitted},
    ApplicationStatus.submitted: {ApplicationStatus.under_review, ApplicationStatus.failed},
    ApplicationStatus.under_review: {
        ApplicationStatus.eligible,
        ApplicationStatus.ineligible,
        ApplicationStatus.offers_ready,
        ApplicationStatus.routed,
        ApplicationStatus.failed,
    },
    ApplicationStatus.eligible: {ApplicationStatus.offers_ready},
    ApplicationStatus.offers_ready: {ApplicationStatus.offer_selected, ApplicationStatus.routed},
    ApplicationStatus.offer_selected: {ApplicationStatus.routed},
    ApplicationStatus.routed: {ApplicationStatus.approved},
}


def can_transition(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def assert_transition(current: ApplicationStatus, target: ApplicationStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(f"Invalid transition from {current.value} to {target.value}")


class ApplicationStateMachine:
    def transition(self, application, next_state: ApplicationStatus):
        assert_transition(application.status, next_state)
        application.status = next_state
        return application
