from types import SimpleNamespace

from app.core.deps import can_access_application, can_view_application
from app.core.exceptions import AppError
from app.core.deps import require_application_access
from app.models.entities import UserRole


def test_sandbox_application_is_public():
    profile = SimpleNamespace(user_id=None)
    assert can_access_application(None, profile) is True


def test_owned_application_requires_owner_or_admin():
    profile = SimpleNamespace(user_id=7)
    owner = SimpleNamespace(id=7, role=UserRole.borrower)
    other = SimpleNamespace(id=8, role=UserRole.borrower)
    admin = SimpleNamespace(id=1, role=UserRole.admin)
    assert can_view_application(owner, profile) is True
    assert can_access_application(owner, profile) is True
    assert can_access_application(other, profile) is False
    assert can_access_application(admin, profile) is True
    try:
        require_application_access(None, profile)
        raise AssertionError("expected auth error")
    except AppError as error:
        assert error.status_code == 401
