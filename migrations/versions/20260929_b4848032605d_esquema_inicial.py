"""esquema inicial

Revision ID: b4848032605d
Revises:
Create Date: 2026-09-29 21:04:16.222819
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4848032605d"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "questions",
        sa.Column("question_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column(
            "question_type",
            sa.Enum("scale", "multiple_choice", "open_text", name="questiontype"),
            nullable=False,
        ),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "compatible_modes",
            sa.Enum("guided", "open", "both", name="compatiblemode"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("question_id", name=op.f("pk_questions")),
        sa.UniqueConstraint("question_text", name=op.f("uq_questions_question_text")),
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("educational_institution", sa.String(length=150), nullable=True),
        sa.Column(
            "role", sa.Enum("student", "evaluator", "admin", name="userrole"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True
    )
    op.create_table(
        "chat_sessions",
        sa.Column("session_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "chat_mode",
            sa.Enum("guided", "open", "mode_selection", name="chatmode"),
            nullable=False,
        ),
        sa.Column(
            "conversation_stage",
            sa.Enum(
                "welcome",
                "mode_choice",
                "questions",
                "collecting",
                "confirm_results",
                "results",
                name="conversationstage",
            ),
            nullable=False,
        ),
        sa.Column("current_question_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "completed", "abandoned", name="sessionstatus"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_activity",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["current_question_id"],
            ["questions.question_id"],
            name=op.f("fk_chat_sessions_current_question_id_questions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_chat_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", name=op.f("pk_chat_sessions")),
    )
    op.create_index(op.f("ix_chat_sessions_user_id"), "chat_sessions", ["user_id"], unique=False)
    op.create_table(
        "evaluator_assignments",
        sa.Column("assignment_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("evaluator_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("active", "inactive", name="assignmentstatus"), nullable=False),
        sa.Column(
            "assigned_date",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evaluator_id"],
            ["users.user_id"],
            name=op.f("fk_evaluator_assignments_evaluator_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.user_id"],
            name=op.f("fk_evaluator_assignments_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("assignment_id", name=op.f("pk_evaluator_assignments")),
        sa.UniqueConstraint(
            "evaluator_id",
            "student_id",
            name=op.f("uq_evaluator_assignments_evaluator_id_student_id"),
        ),
    )
    op.create_index(
        op.f("ix_evaluator_assignments_student_id"),
        "evaluator_assignments",
        ["student_id"],
        unique=False,
    )
    op.create_table(
        "password_resets",
        sa.Column("reset_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_password_resets_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("reset_id", name=op.f("pk_password_resets")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_resets_token_hash")),
    )
    op.create_index(
        op.f("ix_password_resets_user_id"), "password_resets", ["user_id"], unique=False
    )
    op.create_table(
        "chat_messages",
        sa.Column("message_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column(
            "message_type", sa.Enum("user", "bot", "system", name="messagetype"), nullable=False
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_order", sa.Integer(), nullable=False),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.session_id"],
            name=op.f("fk_chat_messages_session_id_chat_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", name=op.f("pk_chat_messages")),
        sa.UniqueConstraint(
            "session_id", "message_order", name=op.f("uq_chat_messages_session_id_message_order")
        ),
    )
    op.create_table(
        "evaluations",
        sa.Column("evaluation_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column(
            "evaluation_mode", sa.Enum("guided", "open", name="evaluationmode"), nullable=False
        ),
        sa.Column(
            "status", sa.Enum("in_progress", "completed", name="evaluationstatus"), nullable=False
        ),
        sa.Column("progress", sa.Double(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("progress BETWEEN 0 AND 1", name=op.f("ck_evaluations_progress_range")),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.session_id"],
            name=op.f("fk_evaluations_session_id_chat_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_evaluations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("evaluation_id", name=op.f("pk_evaluations")),
        sa.UniqueConstraint("session_id", name=op.f("uq_evaluations_session_id")),
    )
    op.create_index(op.f("ix_evaluations_user_id"), "evaluations", ["user_id"], unique=False)
    op.create_table(
        "evaluation_results",
        sa.Column("result_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("riasec_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("top_careers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["evaluations.evaluation_id"],
            name=op.f("fk_evaluation_results_evaluation_id_evaluations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("result_id", name=op.f("pk_evaluation_results")),
        sa.UniqueConstraint("evaluation_id", name=op.f("uq_evaluation_results_evaluation_id")),
    )
    op.create_table(
        "evaluator_comments",
        sa.Column("comment_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("evaluator_id", sa.Integer(), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["evaluations.evaluation_id"],
            name=op.f("fk_evaluator_comments_evaluation_id_evaluations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evaluator_id"],
            ["users.user_id"],
            name=op.f("fk_evaluator_comments_evaluator_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("comment_id", name=op.f("pk_evaluator_comments")),
    )
    op.create_index(
        op.f("ix_evaluator_comments_evaluation_id"),
        "evaluator_comments",
        ["evaluation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluator_comments_evaluator_id"),
        "evaluator_comments",
        ["evaluator_id"],
        unique=False,
    )
    op.create_table(
        "student_feedback",
        sa.Column("feedback_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("dimension_ratings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name=op.f("ck_student_feedback_rating_range")),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["evaluations.evaluation_id"],
            name=op.f("fk_student_feedback_evaluation_id_evaluations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_student_feedback_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("feedback_id", name=op.f("pk_student_feedback")),
        sa.UniqueConstraint(
            "evaluation_id", "user_id", name=op.f("uq_student_feedback_evaluation_id_user_id")
        ),
    )
    op.create_index(
        op.f("ix_student_feedback_user_id"), "student_feedback", ["user_id"], unique=False
    )
    op.create_table(
        "user_answers",
        sa.Column("answer_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("selected_options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["evaluations.evaluation_id"],
            name=op.f("fk_user_answers_evaluation_id_evaluations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.question_id"],
            name=op.f("fk_user_answers_question_id_questions"),
        ),
        sa.PrimaryKeyConstraint("answer_id", name=op.f("pk_user_answers")),
        sa.UniqueConstraint(
            "evaluation_id", "question_id", name=op.f("uq_user_answers_evaluation_id_question_id")
        ),
    )
    op.create_index(
        op.f("ix_user_answers_question_id"), "user_answers", ["question_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_answers_question_id"), table_name="user_answers")
    op.drop_table("user_answers")
    op.drop_index(op.f("ix_student_feedback_user_id"), table_name="student_feedback")
    op.drop_table("student_feedback")
    op.drop_index(op.f("ix_evaluator_comments_evaluator_id"), table_name="evaluator_comments")
    op.drop_index(op.f("ix_evaluator_comments_evaluation_id"), table_name="evaluator_comments")
    op.drop_table("evaluator_comments")
    op.drop_table("evaluation_results")
    op.drop_index(op.f("ix_evaluations_user_id"), table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_table("chat_messages")
    op.drop_index(op.f("ix_password_resets_user_id"), table_name="password_resets")
    op.drop_table("password_resets")
    op.drop_index(op.f("ix_evaluator_assignments_student_id"), table_name="evaluator_assignments")
    op.drop_table("evaluator_assignments")
    op.drop_index(op.f("ix_chat_sessions_user_id"), table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_table("questions")
    for enum_type in (
        "assignmentstatus",
        "chatmode",
        "compatiblemode",
        "conversationstage",
        "evaluationmode",
        "evaluationstatus",
        "messagetype",
        "questiontype",
        "sessionstatus",
        "userrole",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_type}")
