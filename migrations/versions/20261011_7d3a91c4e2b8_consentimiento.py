"""consentimiento

Revision ID: 7d3a91c4e2b8
Revises: 1e8fb0867f62
Create Date: 2026-10-11 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d3a91c4e2b8"
down_revision: str | Sequence[str] | None = "1e8fb0867f62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("consent_accepted_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("consent_version", sa.Integer()))


def downgrade() -> None:
    op.drop_column("users", "consent_version")
    op.drop_column("users", "consent_accepted_at")
