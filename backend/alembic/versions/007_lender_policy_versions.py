"""Versioned lender policies."""

from alembic import op
import sqlalchemy as sa

revision = "007_lender_policy_versions"
down_revision = "006_p0_security_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lender_policy_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lender_id", sa.Integer(), sa.ForeignKey("lenders.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("min_income", sa.Integer(), nullable=True),
        sa.Column("min_credit_score", sa.Integer(), nullable=True),
        sa.Column("max_amount", sa.Integer(), nullable=True),
        sa.Column("max_foir", sa.Float(), nullable=True),
        sa.Column("base_interest_rate", sa.Float(), nullable=True),
        sa.Column("processing_fee", sa.Integer(), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=True),
        sa.Column("journey_score", sa.Float(), nullable=True),
        sa.Column("serves_prime", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("serves_near_prime", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("serves_thin_file", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_lender_policy_versions_lender_id", "lender_policy_versions", ["lender_id"])
    op.create_index("ix_lender_policy_versions_status", "lender_policy_versions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_lender_policy_versions_status", table_name="lender_policy_versions")
    op.drop_index("ix_lender_policy_versions_lender_id", table_name="lender_policy_versions")
    op.drop_table("lender_policy_versions")
