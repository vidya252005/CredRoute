import os
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-for-production-use-only")
os.environ.setdefault("PAN_HMAC_SECRET", "test-pan-hmac-secret-not-for-production")
os.environ.setdefault("ADMIN_EMAIL", "admin@credroute.test")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-local-only")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import session as db_session
from app.db.session import Base, get_db
from app.db.seed import init_db
from app.main import app

SQLITE_PATH = Path(__file__).resolve().parents[2] / ".test_credroute.db"


def resolve_database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return f"sqlite:///{SQLITE_PATH}"


def bind_test_engine(test_engine):
    db_session.engine = test_engine
    db_session.SessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session")
def engine():
    database_url = resolve_database_url()
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    test_engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    bind_test_engine(test_engine)
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    init_db()
    yield test_engine
    if database_url.startswith("sqlite") and SQLITE_PATH.exists():
        SQLITE_PATH.unlink(missing_ok=True)


@pytest.fixture
def client(engine):
    bind_test_engine(engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
