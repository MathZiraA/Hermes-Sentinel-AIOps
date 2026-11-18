"""Multicluster: token do agente por cluster e fila de comandos.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    with op.batch_alter_table("clusters") as batch:
        batch.add_column(sa.Column("agent_token_hash", sa.String(64)))
        batch.add_column(sa.Column("agent_version", sa.String(40)))
    op.create_table(
        "agent_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cluster_id", sa.String(63), sa.ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_id", sa.String(40), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("namespace", sa.String(63), nullable=False, server_default=""),
        sa.Column("workload", sa.String(253), nullable=False),
        sa.Column("pod", sa.String(253), nullable=False, server_default=""),
        sa.Column("resource_kind", sa.String(63), nullable=False, server_default="Pod"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("result", sa.JSON()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_index("ix_agent_commands_cluster_id", "agent_commands", ["cluster_id"])
    op.create_index("ix_agent_commands_incident_id", "agent_commands", ["incident_id"])
    op.create_index("ix_agent_commands_status", "agent_commands", ["status"])


def downgrade() -> None:
    op.drop_table("agent_commands")
    with op.batch_alter_table("clusters") as batch:
        batch.drop_column("agent_version")
        batch.drop_column("agent_token_hash")
