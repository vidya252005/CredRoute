from sqlalchemy import inspect, text

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
                        )
                    )

        admin_email = "admin@credroute.demo"
        if not db.query(User).filter(User.email == admin_email).first():
            db.add(
                User(
                    email=admin_email,
                    hashed_password=hash_password("changeme123"),
                    role=UserRole.admin,
                )
            )
        db.commit()
    finally:
        db.close()
