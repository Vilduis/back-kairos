"""limpiar asignaciones inactivas

Revision ID: 5c1f0e7a9d42
Revises: b4848032605d
Create Date: 2026-10-09 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "5c1f0e7a9d42"
down_revision: str | Sequence[str] | None = "b4848032605d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM evaluator_assignments a
        USING users s, users e
        WHERE s.user_id = a.student_id
          AND e.user_id = a.evaluator_id
          AND (
            NOT s.is_active OR NOT e.is_active
            OR s.role <> 'student' OR e.role <> 'evaluator'
          )
        """
    )


def downgrade() -> None:
    pass
