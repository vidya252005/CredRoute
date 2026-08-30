"""Credit line and consent tables."""

from alembic import op
import sqlalchemy as sa

revision = "002_credit_line_consent"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "borrower_credit_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pan", sa.String(length=10), nullable=False),
        sa.Column("current_limit", sa.Integer(), nullable=False),
        sa.Column("next_limit", sa.Integer(), nullable=False),
        sa.Column("starter_limit", sa.Integer(), nullable=False),
        sa.Column("on_time_repayments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("originated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_originated_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_borrower_credit_lines_pan", "borrower_credit_lines", ["pan"], unique=True)

    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("pan", sa.String(length=10), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_consent_records_application_id", "consent_records", ["application_id"])
    op.create_index("ix_consent_records_pan", "consent_records", ["pan"])


def downgrade() -> None:
    op.drop_table("consent_records")
    op.drop_table("borrower_credit_lines")
