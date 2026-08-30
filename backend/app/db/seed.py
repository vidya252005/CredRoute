from app.core.security import hash_password
from app.data.lenders import LENDER_SEED
from app.db import session as db_session
from app.db.session import Base
from app.models.entities import Lender, User, UserRole
from app.models import warehouse as _warehouse  # noqa: F401 — register warehouse tables on metadata


def init_db() -> None:
    Base.metadata.create_all(bind=db_session.engine)
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
