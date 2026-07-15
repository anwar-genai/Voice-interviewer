"""share_token on interviews (public read-only feedback links)

Revision ID: b41c6f2a9d17
Revises: d5cd8fb878a2
Create Date: 2026-07-15
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b41c6f2a9d17"
down_revision: Union[str, Sequence[str], None] = "d5cd8fb878a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("share_token", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_interviews_share_token"), "interviews", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_interviews_share_token"), table_name="interviews")
    op.drop_column("interviews", "share_token")
