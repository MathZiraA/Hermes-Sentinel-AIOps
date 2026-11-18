"""Esquema inicial: clusters, incidentes, linha do tempo e auditoria imutável.

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "clusters",
        sa.Column("id", sa.String(63), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("context", sa.String(255)),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("last_seen_at", TS),
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("cluster_id", sa.String(63), sa.ForeignKey("clusters.id"), nullable=False),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("sev", sa.String(4), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("namespace", sa.String(63), nullable=False, server_default=""),
        sa.Column("workload", sa.String(253), nullable=False),
        sa.Column("resource_kind", sa.String(63), nullable=False, server_default="Pod"),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("detected_at", TS, nullable=False),
        sa.Column("acknowledged_at", TS),
        sa.Column("resolved_at", TS),
        sa.Column("updated_at", TS, nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    for col in ("cluster_id", "type", "sev", "status", "workload", "detected_at"):
        op.create_index(f"ix_incidents_{col}", "incidents", [col])
    op.create_index("ix_incidents_cluster_status", "incidents", ["cluster_id", "status"])

    op.create_table(
        "incident_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("incident_id", sa.String(40), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ts", TS, nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_index("ix_incident_events_incident_id", "incident_events", ["incident_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", TS, nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target", sa.String(255), nullable=False, server_default=""),
        sa.Column("ip", sa.String(64)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
    )
    for col in ("ts", "actor", "action"):
        op.create_index(f"ix_audit_log_{col}", "audit_log", [col])

    # A trilha de auditoria é append-only: o próprio banco recusa UPDATE e DELETE.
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'audit_log é imutável'; END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            "CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON audit_log "
            "FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();"
        )
    elif dialect == "sqlite":
        for event in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER audit_log_no_{event.lower()} BEFORE {event} ON audit_log "
                "BEGIN SELECT RAISE(ABORT, 'audit_log é imutável'); END;"
            )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_log_no_change ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS audit_log_immutable()")
    for name in ("audit_log", "incident_events", "incidents", "clusters"):
        op.drop_table(name)
