from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.security import hash_password
from app.data.lenders import LENDER_SEED
from app.db import session as db_session
from app.db.session import Base
from app.models.entities import Lender, User, UserRole
from app.models import warehouse as _warehouse  # noqa: F401 — register warehouse tables on metadata


def _add_column_if_missing(engine, table: str, column: str, ddl: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    existing = {item["name"] for item in inspector.get_columns(table)}
    if column in existing:
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def _ensure_schema() -> None:
    engine = db_session.engine
    _add_column_if_missing(engine, "idempotency_keys", "request_hash", "request_hash VARCHAR(64)")
    _add_column_if_missing(engine, "idempotency_keys", "status", "status VARCHAR(30)")
    _add_column_if_missing(engine, "idempotency_keys", "expires_at", "expires_at TIMESTAMP")
    _add_column_if_missing(engine, "borrower_profiles", "pan_hash", "pan_hash VARCHAR(64)")
    _add_column_if_missing(engine, "borrower_credit_lines", "pan_hash", "pan_hash VARCHAR(64)")
    _add_column_if_missing(engine, "borrower_credit_lines", "version", "version INTEGER DEFAULT 0")
    _add_column_if_missing(engine, "consent_records", "pan_hash", "pan_hash VARCHAR(64)")
    _add_column_if_missing(engine, "lenders", "policy_version", "policy_version INTEGER DEFAULT 1")


def _seed_admin(db) -> None:
    email = (settings.admin_email or "").strip().lower()
    password = settings.admin_password
    if not email or not password:
        return
    if db.query(User).filter(User.email == email).first():
        return
    db.add(
        User(
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.admin,
        )
    )


def init_db() -> None:
    Base.metadata.create_all(bind=db_session.engine)
    _ensure_schema()
    db = db_session.SessionLocal()
    try:
        if db.query(Lender).count() == 0:
            for item in LENDER_SEED:
                db.add(
                    Lender(
                        code=item["code"],
                        name=item["name"],
                        category=item["category"],
                        active=True,
                        policy=item,
                        policy_version=1,
                    )
                )
        else:
            existing = {row.code for row in db.query(Lender).all()}
            for item in LENDER_SEED:
                if item["code"] not in existing:
                    db.add(
                        Lender(
                            code=item["code"],
                            name=item["name"],
                            category=item["category"],
                            active=True,
                            policy=item,
                            policy_version=1,
                        )
                    )

        from app.services.lender_policies import sync_seed_policy

        db.flush()
        for lender in db.query(Lender).all():
            sync_seed_policy(db, lender)

        _seed_admin(db)
        db.commit()
    finally:
        db.close()
