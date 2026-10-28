"""add exam results published flag

Revision ID: c37b0e63a001
Revises: 9c6c25f1cda7
Create Date: 2026-10-28

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c37b0e63a001"
down_revision: Union[str, Sequence[str], None] = "9c6c25f1cda7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the result-publication state used by admin and parent APIs."""
    op.add_column(
        "exams",
        sa.Column(
            "results_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    """Remove the result-publication state."""
    op.drop_column("exams", "results_published")
