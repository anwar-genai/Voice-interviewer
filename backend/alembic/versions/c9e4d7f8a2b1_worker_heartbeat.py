"""worker_heartbeat: single-row liveness beacon for the agent worker

Revision ID: c9e4d7f8a2b1
Revises: b41c6f2a9d17
Create Date: 2026-07-16
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e4d7f8a2b1"
down_revision: Union[str, Sequence[str], None] = "b41c6f2a9d17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeat",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("beat_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeat")
