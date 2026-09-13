from app.domain.enums import LenderAttemptStatus
from app.models.entities import Lender, LenderAttemptRecord
from app.routing.coordinator import classify_provider_failure
from app.services.lender_policies import activate_policy, create_draft, list_policies, publish_policy_update
from app.services.reconciliation import reconcile_unknown_attempts
from app.resilience.errors import ProviderTimeout
from app.resilience.retry import RetryPolicy


def test_timeout_is_unknown_not_failed():
    persisted, detail = classify_provider_failure(TimeoutError("simulated lender timeout"))
    assert persisted == LenderAttemptStatus.UNKNOWN
    assert detail == LenderAttemptStatus.FAILED_TIMEOUT
    persisted, _ = classify_provider_failure(ProviderTimeout("deadline"))
    assert persisted == LenderAttemptStatus.UNKNOWN


def test_retry_policy_does_not_retry_keyerror():
    policy = RetryPolicy()
    assert policy.is_retryable(TimeoutError()) is True
    assert policy.is_retryable(KeyError("successRate")) is False


def test_policy_draft_then_activate(engine):
    from sqlalchemy.orm import sessionmaker

    db = sessionmaker(bind=engine)()
    try:
        lender = db.query(Lender).first()
        assert lender is not None
        versions_before = {row.version for row in list_policies(db, lender)}
        draft = create_draft(db, lender, {"min_income": 31000})
        db.commit()
        assert draft.status == "DRAFT"
        assert draft.version not in versions_before or draft.min_income == 31000
        activated = activate_policy(db, lender, draft.version)
        db.commit()
        assert activated.status == "ACTIVE"
        db.refresh(lender)
        assert lender.policy_version == activated.version
        assert lender.policy["min_income"] == 31000
    finally:
        db.close()


def test_publish_policy_update_activates(engine):
    from sqlalchemy.orm import sessionmaker

    db = sessionmaker(bind=engine)()
    try:
        lender = db.query(Lender).first()
        row = publish_policy_update(db, lender, {"processing_fee": 1234})
        db.commit()
        assert row.status == "ACTIVE"
        db.refresh(lender)
        assert lender.policy["processing_fee"] == 1234
    finally:
        db.close()


def test_reconcile_unknown_attempts(engine):
    from sqlalchemy.orm import sessionmaker

    from app.models.entities import BorrowerProfile, LoanApplication

    db = sessionmaker(bind=engine)()
    try:
        profile = BorrowerProfile(
            name="Rekha",
            pan="ABCXX1234X",
            pan_hash="a" * 64,
            age=30,
            income_type="salaried",
            monthly_income=50000,
        )
        db.add(profile)
        db.flush()
        application = LoanApplication(
            borrower_profile_id=profile.id,
            amount=100000,
            tenure_months=12,
        )
        db.add(application)
        db.flush()
        db.add(
            LenderAttemptRecord(
                application_id=application.id,
                lender_code="RURAL-COLENDING-MOCK",
                status="unknown",
                latency_ms=3000,
                error_message="timeout",
            )
        )
        db.commit()
        result = reconcile_unknown_attempts(db)
        assert result["resolved"] >= 1
        row = db.query(LenderAttemptRecord).filter(LenderAttemptRecord.status == "failed").first()
        assert row is not None
        assert row.error_code == "RECONCILED_NO_EXTERNAL_STATE"
    finally:
        db.close()
