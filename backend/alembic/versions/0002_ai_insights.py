"""Add AI insight columns to prescriptions.

Revision ID: 0002_ai_insights
Revises: 0001_initial
Create Date: 2026-11-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_ai_insights"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prescriptions", sa.Column("ai_insights", sa.JSON(), nullable=True))
    op.add_column(
        "prescriptions",
        sa.Column("ai_insights_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "prescriptions",
        sa.Column("ai_insights_model", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "prescriptions",
        sa.Column(
            "ai_insights_generated_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("prescriptions", "ai_insights_generated_at")
    op.drop_column("prescriptions", "ai_insights_model")
    op.drop_column("prescriptions", "ai_insights_status")
    op.drop_column("prescriptions", "ai_insights")
