import pytest

from app.models.entities import ApplicationStatus
from app.services.state_machine import ApplicationStateMachine, can_transition


class _App:
    def __init__(self, status):
        self.status = status


def test_allowed_happy_path():
    assert can_transition(ApplicationStatus.offers_ready, ApplicationStatus.routed)
    assert can_transition(ApplicationStatus.routed, ApplicationStatus.approved)


def test_invalid_transition_is_rejected():
    machine = ApplicationStateMachine()
    app = _App(ApplicationStatus.ineligible)
    with pytest.raises(ValueError, match="Invalid transition"):
        machine.transition(app, ApplicationStatus.routed)
    assert app.status == ApplicationStatus.ineligible


def test_cannot_skip_from_draft_to_approved():
    assert not can_transition(ApplicationStatus.draft, ApplicationStatus.approved)
