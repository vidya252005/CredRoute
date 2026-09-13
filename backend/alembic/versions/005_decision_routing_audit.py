"""Decision audit, routing candidates, and idempotency hash."""

from alembic import op
import sqlalchemy as sa

revision = "005_decision_routing_audit"
down_revision = "004_warehouse_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("idempotency_keys", sa.Column("request_hash", sa.String(length=64), nullable=True))
    op.add_column("idempotency_keys", sa.Column("status", sa.String(length=30), nullable=True))

    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("default_probability", sa.Float(), nullable=True),
        sa.Column("risk_band", sa.String(length=20), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_risk_assessments_application_id", "risk_assessments", ["application_id"])

    op.create_table(
        "fraud_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("fraud_probability", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("flags", sa.JSON(), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_fraud_assessments_application_id", "fraud_assessments", ["application_id"])

    op.create_table(
        "decision_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("policy_version", sa.String(length=50), nullable=True),
        sa.Column("routing_version", sa.String(length=50), nullable=True),
        sa.Column("feature_snapshot", sa.JSON(), nullable=True),
        sa.Column("lender_results", sa.JSON(), nullable=True),
        sa.Column("final_decision", sa.String(length=32), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("explainability", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_decision_audits_application_id", "decision_audits", ["application_id"])

    op.create_table(
        "lender_attempt_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("lender_code", sa.String(length=64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_lender_attempt_records_application_id", "lender_attempt_records", ["application_id"])
    op.create_index("ix_lender_attempt_records_lender_code", "lender_attempt_records", ["lender_code"])

    op.create_table(
        "routing_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("selected_offer_id", sa.Integer(), nullable=True),
        sa.Column("selected_lender", sa.String(length=64), nullable=True),
        sa.Column("strategy", sa.String(length=50), nullable=True),
        sa.Column("strategy_version", sa.String(length=50), nullable=True),
        sa.Column("policy_version", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_routing_decisions_application_id", "routing_decisions", ["application_id"])

    op.create_table(
        "routing_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("decision_id", sa.Integer(), sa.ForeignKey("routing_decisions.id"), nullable=False),
        sa.Column("lender_code", sa.String(length=64), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("rejection_reasons", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
    )
    op.create_index("ix_routing_candidates_decision_id", "routing_candidates", ["decision_id"])


def downgrade() -> None:
    op.drop_index("ix_routing_candidates_decision_id", table_name="routing_candidates")
    op.drop_table("routing_candidates")
    op.drop_index("ix_routing_decisions_application_id", table_name="routing_decisions")
    op.drop_table("routing_decisions")
    op.drop_index("ix_lender_attempt_records_lender_code", table_name="lender_attempt_records")
    op.drop_index("ix_lender_attempt_records_application_id", table_name="lender_attempt_records")
    op.drop_table("lender_attempt_records")
    op.drop_index("ix_decision_audits_application_id", table_name="decision_audits")
    op.drop_table("decision_audits")
    op.drop_index("ix_fraud_assessments_application_id", table_name="fraud_assessments")
    op.drop_table("fraud_assessments")
    op.drop_index("ix_risk_assessments_application_id", table_name="risk_assessments")
    op.drop_table("risk_assessments")
    op.drop_column("idempotency_keys", "status")
    op.drop_column("idempotency_keys", "request_hash")
