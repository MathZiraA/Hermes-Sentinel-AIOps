"""Operação: silêncios, políticas de autorremediação e plantão.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "silences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cluster_id", sa.String(63), nullable=False, server_default="*"),
        sa.Column("namespace", sa.String(63), nullable=False, server_default="*"),
        sa.Column("workload", sa.String(253), nullable=False, server_default="*"),
        sa.Column("incident_type", sa.String(80), nullable=False, server_default="*"),
        sa.Column("starts_at", TS, nullable=False),
        sa.Column("ends_at", TS, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_silences_ends_at", "silences", ["ends_at"])
    op.create_table(
        "remediation_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cluster_id", sa.String(63), nullable=False, server_default="*"),
        sa.Column("namespace", sa.String(63), nullable=False, server_default="*"),
        sa.Column("workload", sa.String(253), nullable=False, server_default="*"),
        sa.Column("incident_type", sa.String(80), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("max_per_hour", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_table(
        "oncall_shifts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_email", sa.String(254), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("starts_at", TS, nullable=False),
        sa.Column("ends_at", TS, nullable=False),
    )
    op.create_index("ix_oncall_shifts_team_id", "oncall_shifts", ["team_id"])
    op.create_index("ix_oncall_shifts_ends_at", "oncall_shifts", ["ends_at"])


def downgrade() -> None:
    for name in ("oncall_shifts", "remediation_policies", "silences"):
        op.drop_table(name)
