"""add operational email policy and suppression records

Revision ID: a7b8c9d0e1f2
Revises: f5b2c3d4e5f6
Create Date: 2026-11-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f5b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_notification_batches",
        sa.Column(
            "recipient_policy",
            sa.String(length=20),
            nullable=False,
            server_default="OPTIONAL",
        ),
    )
    op.add_column(
        "email_notification_batches",
        sa.Column("event_reference", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_email_notification_batches_event_reference",
        "email_notification_batches",
        ["event_reference"],
        unique=False,
    )
    for name in (
        "suppressed_email_count",
        "verified_email_recipient_count",
        "unverified_email_recipient_count",
    ):
        op.add_column(
            "email_notification_batches",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )

    op.create_table(
        "email_suppressions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column(
            "source",
            sa.String(length=40),
            nullable=False,
            server_default="MANUAL",
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_email_suppressions_email", "email_suppressions", ["email"], unique=True
    )
    op.create_index(
        "ix_email_suppressions_is_active",
        "email_suppressions",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_suppressions_is_active", table_name="email_suppressions")
    op.drop_index("ix_email_suppressions_email", table_name="email_suppressions")
    op.drop_table("email_suppressions")
    op.drop_index(
        "ix_email_notification_batches_event_reference",
        table_name="email_notification_batches",
    )
    for name in (
        "unverified_email_recipient_count",
        "verified_email_recipient_count",
        "suppressed_email_count",
        "recipient_policy",
    ):
        op.drop_column("email_notification_batches", name)
    op.drop_column("email_notification_batches", "event_reference")
