"""colegios

Revision ID: 1e8fb0867f62
Revises: 5c1f0e7a9d42
Create Date: 2026-10-11 14:41:31.149904
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1e8fb0867f62"
down_revision: str | Sequence[str] | None = "5c1f0e7a9d42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_SCHOOL = "Kairos Demo"


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'school_admin' BEFORE 'admin'")
    op.create_table(
        "schools",
        sa.Column("school_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("school_id", name=op.f("pk_schools")),
    )
    op.create_index(
        "uq_schools_name_lower", "schools", [sa.literal_column("lower(name)")], unique=True
    )

    op.add_column("users", sa.Column("school_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_users_school_id"), "users", ["school_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_users_school_id_schools"),
        "users",
        "schools",
        ["school_id"],
        ["school_id"],
        ondelete="RESTRICT",
    )
    # Los usuarios previos a los colegios quedan en uno de prueba; el superadmin los mueve después.
    op.execute(
        sa.text(
            """
            WITH demo AS (INSERT INTO schools (name) VALUES (:name) RETURNING school_id)
            UPDATE users SET school_id = (SELECT school_id FROM demo) WHERE role <> 'admin'
            """
        ).bindparams(name=DEMO_SCHOOL)
    )
    op.create_check_constraint(
        op.f("ck_users_school_matches_role"), "users", "(role = 'admin') = (school_id IS NULL)"
    )
    op.drop_column("users", "educational_institution")

    op.create_table(
        "school_access_codes",
        sa.Column("code_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=9), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("evaluator_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("uses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "max_uses IS NULL OR max_uses > 0",
            name=op.f("ck_school_access_codes_max_uses_positive"),
        ),
        sa.CheckConstraint("uses >= 0", name=op.f("ck_school_access_codes_uses_not_negative")),
        sa.ForeignKeyConstraint(
            ["evaluator_id"],
            ["users.user_id"],
            name=op.f("fk_school_access_codes_evaluator_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["schools.school_id"],
            name=op.f("fk_school_access_codes_school_id_schools"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("code_id", name=op.f("pk_school_access_codes")),
        sa.UniqueConstraint("code", name=op.f("uq_school_access_codes_code")),
    )
    op.create_index(
        op.f("ix_school_access_codes_school_id"), "school_access_codes", ["school_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_school_access_codes_school_id"), table_name="school_access_codes")
    op.drop_table("school_access_codes")

    op.add_column(
        "users",
        sa.Column("educational_institution", sa.VARCHAR(length=150), nullable=True),
    )
    op.execute(
        """
        UPDATE users u SET educational_institution = s.name
        FROM schools s WHERE s.school_id = u.school_id
        """
    )
    # PostgreSQL no permite quitar un valor de un enum: los administradores de colegio
    # pasan a evaluadores para que el código anterior pueda leerlos.
    op.execute("UPDATE users SET role = 'evaluator' WHERE role = 'school_admin'")
    op.drop_constraint(op.f("ck_users_school_matches_role"), "users", type_="check")
    op.drop_constraint(op.f("fk_users_school_id_schools"), "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_school_id"), table_name="users")
    op.drop_column("users", "school_id")
    op.drop_index("uq_schools_name_lower", table_name="schools")
    op.drop_table("schools")
