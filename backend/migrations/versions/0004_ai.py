"""IA: consumo diário por provedor e índice do Hermes Brain.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("provider", sa.String(40), primary_key=True),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "brain_notes",
        sa.Column("name", sa.String(255), primary_key=True),
        sa.Column("folder", sa.String(120), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("mtime", sa.Float(), nullable=False),
        sa.Column("embedding", sa.JSON()),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("brain_notes")
    op.drop_table("ai_usage")
