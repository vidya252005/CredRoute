"""Alembic 003 — use IF NOT EXISTS so create_all + migrate both work."""

from alembic import op

revision = "003_warehouse_and_indexes"
down_revision = "002_credit_line_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_loan_applications_borrower_profile_id ON loan_applications (borrower_profile_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_loan_applications_status ON loan_applications (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_loan_applications_created_at ON loan_applications (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_loan_applications_status_created ON loan_applications (status, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_application_events_event_type ON application_events (event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_application_events_type_created ON application_events (event_type, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_borrower_profiles_income_city ON borrower_profiles (income_type, city_tier)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_borrowers (
            id SERIAL PRIMARY KEY,
            pan VARCHAR(10) NOT NULL,
            age INTEGER NOT NULL,
            income_type VARCHAR(32) NOT NULL,
            monthly_income INTEGER NOT NULL,
            cibil_score INTEGER,
            city_tier INTEGER NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_loans (
            id SERIAL PRIMARY KEY,
            borrower_id INTEGER NOT NULL REFERENCES warehouse_borrowers(id),
            amount INTEGER NOT NULL,
            tenure_months INTEGER NOT NULL,
            status VARCHAR(32) NOT NULL,
            interest_rate FLOAT NOT NULL,
            originated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_transactions (
            id SERIAL PRIMARY KEY,
            loan_id INTEGER NOT NULL REFERENCES warehouse_loans(id),
            borrower_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            txn_type VARCHAR(24) NOT NULL,
            posted_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_applications (
            id SERIAL PRIMARY KEY,
            borrower_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            decision VARCHAR(16) NOT NULL,
            default_probability FLOAT NOT NULL,
            fraud_probability FLOAT NOT NULL,
            explained INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS warehouse_applications")
    op.execute("DROP TABLE IF EXISTS warehouse_transactions")
    op.execute("DROP TABLE IF EXISTS warehouse_loans")
    op.execute("DROP TABLE IF EXISTS warehouse_borrowers")
    op.execute("DROP INDEX IF EXISTS ix_borrower_profiles_income_city")
    op.execute("DROP INDEX IF EXISTS ix_application_events_type_created")
    op.execute("DROP INDEX IF EXISTS ix_application_events_event_type")
    op.execute("DROP INDEX IF EXISTS ix_loan_applications_status_created")
    op.execute("DROP INDEX IF EXISTS ix_loan_applications_created_at")
    op.execute("DROP INDEX IF EXISTS ix_loan_applications_status")
    op.execute("DROP INDEX IF EXISTS ix_loan_applications_borrower_profile_id")
