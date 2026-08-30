"""Initial CredRoute schema."""

from alembic import op
import sqlalchemy as sa

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("borrower", "admin", name="userrole"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "borrower_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("pan", sa.String(length=10), nullable=False),
        sa.Column("age", sa.Integer()),
        sa.Column("income_type", sa.String(length=32), nullable=False),
        sa.Column("monthly_income", sa.Integer(), nullable=False),
        sa.Column("cibil_score", sa.Integer(), nullable=True),
        sa.Column("existing_emis", sa.Integer(), nullable=False),
        sa.Column("bank_statement_avg_balance", sa.Integer(), nullable=False),
        sa.Column("city_tier", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_borrower_profiles_pan", "borrower_profiles", ["pan"])

    op.create_table(
        "lenders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_lenders_code", "lenders", ["code"], unique=True)

    op.create_table(
        "loan_applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("borrower_profile_id", sa.Integer(), sa.ForeignKey("borrower_profiles.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("tenure_months", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum(
            "draft", "submitted", "under_review", "eligible", "offers_ready", "ineligible",
            "offer_selected", "routed", "approved", "rejected", "expired", "failed",
            name="applicationstatus",
        ), nullable=False),
        sa.Column("eligibility", sa.JSON(), nullable=True),
        sa.Column("risk", sa.JSON(), nullable=True),
        sa.Column("lender_attempts", sa.JSON(), nullable=True),
        sa.Column("routed_lender_code", sa.String(length=64), nullable=True),
        sa.Column("selected_offer_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_loan_applications_idempotency_key", "loan_applications", ["idempotency_key"], unique=True)

    op.create_table(
        "loan_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("lender_id", sa.Integer(), sa.ForeignKey("lenders.id"), nullable=False),
        sa.Column("lender_code", sa.String(length=64), nullable=False),
        sa.Column("lender_name", sa.String(length=120), nullable=False),
        sa.Column("interest_rate", sa.Float(), nullable=False),
        sa.Column("processing_fee", sa.Integer(), nullable=False),
        sa.Column("approval_probability", sa.Float(), nullable=False),
        sa.Column("max_amount", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("monthly_payment", sa.Integer(), nullable=False),
        sa.Column("routing_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_loan_offers_application_id", "loan_offers", ["application_id"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_application_events_application_id", "application_events", ["application_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_idempotency_keys_key", "idempotency_keys", ["key"], unique=True)


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("application_events")
    op.drop_table("loan_offers")
    op.drop_table("loan_applications")
    op.drop_table("lenders")
    op.drop_table("borrower_profiles")
    op.drop_table("users")
