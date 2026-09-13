"""PAN hashes, idempotency TTL, outbox, policy version, credit-line version."""

from alembic import op
import sqlalchemy as sa

revision = "006_p0_security_integrity"
down_revision = "005_decision_routing_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("borrower_profiles", sa.Column("pan_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_borrower_profiles_pan_hash", "borrower_profiles", ["pan_hash"])

    op.add_column("borrower_credit_lines", sa.Column("pan_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "borrower_credit_lines",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_borrower_credit_lines_pan_hash", "borrower_credit_lines", ["pan_hash"], unique=True)
    op.drop_index("ix_borrower_credit_lines_pan", table_name="borrower_credit_lines")
    op.create_index("ix_borrower_credit_lines_pan", "borrower_credit_lines", ["pan"], unique=False)

    op.add_column("consent_records", sa.Column("pan_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_consent_records_pan_hash", "consent_records", ["pan_hash"])

    op.add_column(
        "lenders",
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("idempotency_keys", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_column("idempotency_keys", "expires_at")
    op.drop_column("lenders", "policy_version")
    op.drop_index("ix_consent_records_pan_hash", table_name="consent_records")
    op.drop_column("consent_records", "pan_hash")
    op.drop_index("ix_borrower_credit_lines_pan", table_name="borrower_credit_lines")
    op.create_index("ix_borrower_credit_lines_pan", "borrower_credit_lines", ["pan"], unique=True)
    op.drop_index("ix_borrower_credit_lines_pan_hash", table_name="borrower_credit_lines")
    op.drop_column("borrower_credit_lines", "version")
    op.drop_column("borrower_credit_lines", "pan_hash")
    op.drop_index("ix_borrower_profiles_pan_hash", table_name="borrower_profiles")
    op.drop_column("borrower_profiles", "pan_hash")
