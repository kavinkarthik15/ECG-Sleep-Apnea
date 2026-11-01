"""Create visitor sessions and persisted ECG analyses.

Revision ID: 20261101_01
Revises:
Create Date: 2026-11-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261101_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visitor_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'expired')",
            name="ck_visitor_sessions_status",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_visitor_sessions_expiry"),
        sa.UniqueConstraint("session_id_hash", name="uq_visitor_sessions_session_id_hash"),
    )
    op.create_index(
        "ix_visitor_sessions_status_expiry_activity",
        "visitor_sessions",
        ["status", "expires_at", "last_activity_at"],
    )
    op.create_table(
        "ecg_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_ref", sa.String(length=64), nullable=False),
        sa.Column("visitor_session_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("sampling_rate", sa.SmallInteger(), nullable=False),
        sa.Column("window_seconds", sa.SmallInteger(), nullable=False),
        sa.Column("ignored_samples", sa.Integer(), nullable=False),
        sa.Column("ignored_seconds", sa.Float(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("windows", sa.JSON(), nullable=False),
        sa.CheckConstraint("sampling_rate > 0", name="ck_ecg_analyses_sampling_rate"),
        sa.CheckConstraint("window_seconds > 0", name="ck_ecg_analyses_window_seconds"),
        sa.CheckConstraint("ignored_samples >= 0", name="ck_ecg_analyses_ignored_samples"),
        sa.ForeignKeyConstraint(
            ["visitor_session_id"],
            ["visitor_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("public_ref", name="uq_ecg_analyses_public_ref"),
    )
    op.create_index(
        "ix_ecg_analyses_visitor_session_id",
        "ecg_analyses",
        ["visitor_session_id"],
    )
    op.create_index(
        "ix_ecg_analyses_session_created",
        "ecg_analyses",
        ["visitor_session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ecg_analyses_session_created", table_name="ecg_analyses")
    op.drop_index("ix_ecg_analyses_visitor_session_id", table_name="ecg_analyses")
    op.drop_table("ecg_analyses")
    op.drop_index("ix_visitor_sessions_status_expiry_activity", table_name="visitor_sessions")
    op.drop_table("visitor_sessions")
