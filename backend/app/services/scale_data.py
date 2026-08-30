"""Generate synthetic warehouse history for query benchmarks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy import text

from app.db.session import Base, engine
from app.models import warehouse as _warehouse  # noqa: F401

SCALES = {
    "quick": {"borrowers": 2_000, "loans": 10_000, "transactions": 20_000, "applications": 500},
    "full": {"borrowers": 100_000, "loans": 500_000, "transactions": 1_000_000, "applications": 10_000},
}

WAREHOUSE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_wh_borrowers_pan ON warehouse_borrowers (pan)",
    "CREATE INDEX IF NOT EXISTS ix_wh_loans_borrower_originated ON warehouse_loans (borrower_id, originated_at)",
    "CREATE INDEX IF NOT EXISTS ix_wh_loans_status ON warehouse_loans (status)",
    "CREATE INDEX IF NOT EXISTS ix_wh_txn_loan_posted ON warehouse_transactions (loan_id, posted_at)",
    "CREATE INDEX IF NOT EXISTS ix_wh_txn_borrower_posted ON warehouse_transactions (borrower_id, posted_at)",
    "CREATE INDEX IF NOT EXISTS ix_wh_txn_type ON warehouse_transactions (txn_type)",
    "CREATE INDEX IF NOT EXISTS ix_wh_apps_borrower ON warehouse_applications (borrower_id)",
    "CREATE INDEX IF NOT EXISTS ix_wh_apps_decision ON warehouse_applications (decision)",
]

DROP_WAREHOUSE_INDEXES = [
    "DROP INDEX IF EXISTS ix_wh_apps_decision",
    "DROP INDEX IF EXISTS ix_wh_apps_borrower",
    "DROP INDEX IF EXISTS ix_wh_txn_type",
    "DROP INDEX IF EXISTS ix_wh_txn_borrower_posted",
    "DROP INDEX IF EXISTS ix_wh_txn_loan_posted",
    "DROP INDEX IF EXISTS ix_wh_loans_status",
    "DROP INDEX IF EXISTS ix_wh_loans_borrower_originated",
    "DROP INDEX IF EXISTS ix_wh_borrowers_pan",
]

HISTORY_SQL = """
SELECT b.pan,
       COUNT(DISTINCT l.id) AS loan_count,
       COALESCE(SUM(l.amount), 0) AS loan_volume,
       COUNT(t.id) AS txn_count
FROM warehouse_borrowers b
JOIN warehouse_loans l ON l.borrower_id = b.id
LEFT JOIN warehouse_transactions t ON t.loan_id = l.id
WHERE b.pan = :pan
GROUP BY b.pan
"""


def pan_for(index: int) -> str:
    letters = "".join(chr(65 + ((index // (26**p)) % 26)) for p in range(5))
    return f"{letters}{index % 10000:04d}{chr(65 + (index % 26))}"


def _bind(bind=None):
    return bind if bind is not None else engine


def ensure_tables(bind=None) -> None:
    Base.metadata.create_all(bind=_bind(bind))


def _truncate(conn, bind=None) -> None:
    if _bind(bind).dialect.name == "postgresql":
        conn.execute(
            text(
                "TRUNCATE warehouse_applications, warehouse_transactions, warehouse_loans, warehouse_borrowers RESTART IDENTITY CASCADE"
            )
        )
        return
    for table in (
        "warehouse_applications",
        "warehouse_transactions",
        "warehouse_loans",
        "warehouse_borrowers",
    ):
        conn.execute(text(f"DELETE FROM {table}"))


def _insert(conn, table: str, columns: list[str], rows: list[tuple], chunk: int = 5000) -> None:
    if not rows:
        return
    placeholders = ", ".join([f":c{i}" for i in range(len(columns))])
    stmt = text(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})")
    for start in range(0, len(rows), chunk):
        batch = rows[start : start + chunk]
        payload = [{f"c{i}": value for i, value in enumerate(row)} for row in batch]
        conn.execute(stmt, payload)


def generate_scale_data(mode: str = "quick", seed: int = 42, bind=None) -> dict:
    spec = SCALES[mode]
    rng = np.random.default_rng(seed)
    n_b = spec["borrowers"]
    n_l = spec["loans"]
    n_t = spec["transactions"]
    n_a = spec["applications"]
    db = _bind(bind)
    ensure_tables(db)

    income_types = np.array(["salaried", "self_employed", "gig", "msme"])
    statuses = np.array(["closed", "active", "charged_off"])
    txn_types = np.array(["disbursement", "emi", "fee", "bounce"])
    decisions = np.array(["approve", "review", "reject"])
    origin = datetime(2022, 1, 1, tzinfo=UTC)

    borrowers = [
        (
            i + 1,
            pan_for(i),
            int(rng.integers(21, 61)),
            str(rng.choice(income_types, p=[0.55, 0.2, 0.15, 0.1])),
            int(np.clip(rng.lognormal(10.4, 0.5), 18000, 350000)),
            int(rng.integers(300, 861)),
            int(rng.choice([1, 2, 3], p=[0.45, 0.35, 0.2])),
        )
        for i in range(n_b)
    ]
    borrower_ids = np.array([row[0] for row in borrowers])

    loan_borrower_ids = rng.choice(borrower_ids, size=n_l)
    loans = [
        (
            i + 1,
            int(loan_borrower_ids[i]),
            int(rng.choice([50000, 100000, 200000, 400000, 750000])),
            int(rng.choice([12, 18, 24, 36])),
            str(rng.choice(statuses, p=[0.55, 0.4, 0.05])),
            float(rng.uniform(11.5, 22.0)),
            origin + timedelta(days=int(rng.integers(0, 1000))),
        )
        for i in range(n_l)
    ]

    transactions = []
    for i in range(n_t):
        loan_id = int(rng.integers(1, n_l + 1))
        transactions.append(
            (
                i + 1,
                loan_id,
                int(loans[loan_id - 1][1]),
                int(rng.integers(500, 25000)),
                str(rng.choice(txn_types, p=[0.1, 0.75, 0.1, 0.05])),
                origin + timedelta(days=int(rng.integers(0, 1100))),
            )
        )

    applications = [
        (
            i + 1,
            int(rng.integers(1, n_b + 1)),
            int(rng.choice([50000, 150000, 300000])),
            str(rng.choice(decisions, p=[0.62, 0.18, 0.2])),
            float(rng.uniform(0.04, 0.45)),
            float(rng.uniform(0.02, 0.4)),
            1,
        )
        for i in range(n_a)
    ]

    with db.begin() as conn:
        _truncate(conn, db)
        _insert(
            conn,
            "warehouse_borrowers",
            ["id", "pan", "age", "income_type", "monthly_income", "cibil_score", "city_tier"],
            borrowers,
        )
        _insert(
            conn,
            "warehouse_loans",
            ["id", "borrower_id", "amount", "tenure_months", "status", "interest_rate", "originated_at"],
            loans,
        )
        _insert(
            conn,
            "warehouse_transactions",
            ["id", "loan_id", "borrower_id", "amount", "txn_type", "posted_at"],
            transactions,
        )
        _insert(
            conn,
            "warehouse_applications",
            ["id", "borrower_id", "amount", "decision", "default_probability", "fraud_probability", "explained"],
            applications,
        )

    return {
        "mode": mode,
        "borrowers": n_b,
        "loans": n_l,
        "transactions": n_t,
        "applications": n_a,
        "samplePan": pan_for(0),
        "dialect": db.dialect.name,
    }


def drop_warehouse_indexes(bind=None) -> None:
    with _bind(bind).begin() as conn:
        for stmt in DROP_WAREHOUSE_INDEXES:
            conn.execute(text(stmt))


def create_warehouse_indexes(bind=None) -> None:
    with _bind(bind).begin() as conn:
        for stmt in WAREHOUSE_INDEXES:
            conn.execute(text(stmt))


def analyze_warehouse(bind=None) -> None:
    db = _bind(bind)
    if db.dialect.name != "postgresql":
        return
    with db.begin() as conn:
        for table in (
            "warehouse_borrowers",
            "warehouse_loans",
            "warehouse_transactions",
            "warehouse_applications",
        ):
            conn.execute(text(f"ANALYZE {table}"))
