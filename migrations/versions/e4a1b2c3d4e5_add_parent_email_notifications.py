"""add parent email notification outbox

Revision ID: e4a1b2c3d4e5
Revises: c37b0e63a001
Create Date: 2026-11-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "c37b0e63a001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_table(
        "email_notification_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("send_in_app", sa.Boolean(), nullable=False),
        sa.Column("send_email", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("parent_recipient_count", sa.Integer(), nullable=False),
        sa.Column("email_recipient_count", sa.Integer(), nullable=False),
        sa.Column("missing_email_count", sa.Integer(), nullable=False),
        sa.Column("invalid_email_count", sa.Integer(), nullable=False),
        sa.Column("unverified_email_count", sa.Integer(), nullable=False),
        sa.Column("opted_out_count", sa.Integer(), nullable=False),
        sa.Column("deduplicated_email_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_notification_batches_idempotency_key",
        "email_notification_batches",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_email_notification_batches_status",
        "email_notification_batches",
        ["status"],
        unique=False,
    )

    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("parent_user_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["email_notification_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "email", name="uq_email_delivery_batch_email"),
    )
    op.create_index("ix_email_deliveries_batch_id", "email_deliveries", ["batch_id"])
    op.create_index("ix_email_deliveries_parent_user_id", "email_deliveries", ["parent_user_id"])
    op.create_index("ix_email_deliveries_status", "email_deliveries", ["status"])
    op.create_index("ix_email_deliveries_next_attempt_at", "email_deliveries", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_email_deliveries_next_attempt_at", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_status", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_parent_user_id", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_batch_id", table_name="email_deliveries")
    op.drop_table("email_deliveries")
    op.drop_index("ix_email_notification_batches_status", table_name="email_notification_batches")
    op.drop_index("ix_email_notification_batches_idempotency_key", table_name="email_notification_batches")
    op.drop_table("email_notification_batches")
    op.drop_column("users", "email_notifications_enabled")
    op.drop_column("users", "email_verified_at")
