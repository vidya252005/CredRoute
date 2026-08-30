from alembic import op

revision = "004_warehouse_indexes"
down_revision = "003_warehouse_and_indexes"
branch_labels = None
depends_on = None

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_wh_borrowers_pan ON warehouse_borrowers (pan)",
    "CREATE INDEX IF NOT EXISTS ix_wh_loans_borrower_originated ON warehouse_loans (borrower_id, originated_at)",
    "CREATE INDEX IF NOT EXISTS ix_wh_loans_status ON warehouse_loans (status)",
    "CREATE INDEX IF NOT EXISTS ix_wh_txn_loan_posted ON warehouse_transactions (loan_id, posted_at)",
    "CREATE INDEX IF NOT EXISTS ix_wh_txn_borrower_posted ON warehouse_transactions (borrower_id, posted_at)",
    "CREATE INDEX IF NOT EXISTS ix_wh_txn_type ON warehouse_transactions (txn_type)",
    "CREATE INDEX IF NOT EXISTS ix_wh_apps_borrower ON warehouse_applications (borrower_id)",
    "CREATE INDEX IF NOT EXISTS ix_wh_apps_decision ON warehouse_applications (decision)",
]


def upgrade() -> None:
    for stmt in INDEXES:
        op.execute(stmt)


def downgrade() -> None:
    for name in (
        "ix_wh_apps_decision",
        "ix_wh_apps_borrower",
        "ix_wh_txn_type",
        "ix_wh_txn_borrower_posted",
        "ix_wh_txn_loan_posted",
        "ix_wh_loans_status",
        "ix_wh_loans_borrower_originated",
        "ix_wh_borrowers_pan",
    ):
        op.execute(f"DROP INDEX IF EXISTS {name}")
