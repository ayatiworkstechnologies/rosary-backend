"""add notifications table

Revision ID: 9c6c25f1cda7
Revises: 6f31cdd8d471
Create Date: 2026-10-06 12:36:30.543554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c6c25f1cda7'
down_revision: Union[str, Sequence[str], None] = '6f31cdd8d471'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notifications table."""

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "notification_type",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "reference_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "link",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_notifications_id",
        "notifications",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_user_id",
        "notifications",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove notifications table."""

    op.drop_index(
        "ix_notifications_user_id",
        table_name="notifications",
    )

    op.drop_index(
        "ix_notifications_id",
        table_name="notifications",
    )

    op.drop_table("notifications")
