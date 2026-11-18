"""Tabelas do Hermes Sentinel (SQLAlchemy 2). PostgreSQL em produção, SQLite na demo e nos testes.

O incidente guarda colunas para filtrar e relatar (status, severidade, datas) e o documento
completo em `data` (JSON): o contrato pydantic `schemas.events.Incident` continua sendo a fonte da verdade.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[Any]: JSON}


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[str] = mapped_column(String(63), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    context: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IncidentRow(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    cluster_id: Mapped[str] = mapped_column(ForeignKey("clusters.id"), index=True)
    type: Mapped[str] = mapped_column(String(80), index=True)
    sev: Mapped[str] = mapped_column(String(4), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    namespace: Mapped[str] = mapped_column(String(63), default="")
    workload: Mapped[str] = mapped_column(String(253), index=True)
    resource_kind: Mapped[str] = mapped_column(String(63), default="Pod")
    simulated: Mapped[bool] = mapped_column(default=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)

    __table_args__ = (Index("ix_incidents_cluster_status", "cluster_id", "status"),)


class IncidentEvent(Base):
    """Linha do tempo do incidente (append-only)."""

    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(String(120), default="sistema")
    kind: Mapped[str] = mapped_column(String(40), default="note")
    text: Mapped[str] = mapped_column(Text)


class AuditEntry(Base):
    """Trilha de auditoria imutável: cada linha carrega o hash da anterior (cadeia SHA-256).

    UPDATE e DELETE são bloqueados por trigger no banco (ver migração 0001).
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target: Mapped[str] = mapped_column(String(255), default="")
    ip: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


# --------------------------------------------------------------------------- identidade (Fase 2)
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16))  # admin | operator | viewer | auditor
    password_hash: Mapped[str | None] = mapped_column(String(255))  # vazio = só SSO
    totp_secret: Mapped[str | None] = mapped_column(String(255))  # cifrado (Fernet)
    oidc_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TeamMember(Base):
    __tablename__ = "team_members"

    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class TeamScope(Base):
    """O que o time enxerga e opera: cluster e namespace ("*" = todos)."""

    __tablename__ = "team_scopes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    cluster_id: Mapped[str] = mapped_column(String(63), default="*")
    namespace: Mapped[str] = mapped_column(String(63), default="*")


class SessionRow(Base):
    """Sessão de login. Só o SHA-256 do token fica no banco; o token vive num cookie HttpOnly."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(token)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    revoked: Mapped[bool] = mapped_column(default=False)
