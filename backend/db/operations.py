"""Operação: silêncios (janelas de manutenção), políticas de autorremediação e plantão."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from typing import Any

from sqlalchemy import delete, select

from db import engine as db
from db.models import OnCallShift, RemediationPolicy, Silence, Team, TeamMember, TeamScope, User, utcnow
from domain.actions import ACTIONS, InvalidAction


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


def _iso(dt: datetime | None) -> str | None:
    return _aware(dt).isoformat() if dt else None  # type: ignore[union-attr]


def _match(pattern: str, value: str) -> bool:
    return pattern in ("*", "") or fnmatchcase(value or "", pattern)


# --------------------------------------------------------------------------- silêncios
def _silence_dict(s: Silence) -> dict[str, Any]:
    now = utcnow()
    return {
        "id": s.id,
        "cluster": s.cluster_id,
        "namespace": s.namespace,
        "workload": s.workload,
        "type": s.incident_type,
        "startsAt": _iso(s.starts_at),
        "endsAt": _iso(s.ends_at),
        "active": (_aware(s.starts_at) or now) <= now < (_aware(s.ends_at) or now),
        "reason": s.reason,
        "createdBy": s.created_by,
    }


async def create_silence(
    *,
    cluster: str,
    namespace: str,
    workload: str,
    incident_type: str,
    starts_at: datetime,
    ends_at: datetime,
    reason: str,
    created_by: str,
) -> dict[str, Any]:
    if ends_at <= starts_at:
        raise ValueError("o fim precisa ser depois do início")
    if (ends_at - starts_at).days > 30:
        raise ValueError("uma janela de manutenção dura no máximo 30 dias")
    if not reason.strip():
        raise ValueError("informe o motivo (ex.: deploy planejado, manutenção do banco)")
    row = Silence(
        id=str(uuid.uuid4()),
        cluster_id=cluster or "*",
        namespace=namespace or "*",
        workload=workload or "*",
        incident_type=incident_type or "*",
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason.strip()[:500],
        created_by=created_by,
    )
    async with db.session() as s:
        s.add(row)
        await s.commit()
    return _silence_dict(row)


async def list_silences(include_expired: bool = False) -> list[dict[str, Any]]:
    stmt = select(Silence).order_by(Silence.ends_at.desc())
    if not include_expired:
        stmt = stmt.where(Silence.ends_at > utcnow())
    async with db.session() as s:
        return [_silence_dict(r) for r in (await s.scalars(stmt)).all()]


async def expire_silence(silence_id: str) -> bool:
    async with db.session() as s:
        row = await s.get(Silence, silence_id)
        if not row:
            return False
        row.ends_at = utcnow()
        await s.commit()
    return True


async def active_silence(cluster: str, namespace: str, workload: str, incident_type: str) -> dict[str, Any] | None:
    """O silêncio ativo que cobre este sinal, se houver."""
    now = utcnow()
    async with db.session() as s:
        rows = (await s.scalars(select(Silence).where(Silence.ends_at > now, Silence.starts_at <= now))).all()
    for r in rows:
        if (
            _match(r.cluster_id, cluster)
            and _match(r.namespace, namespace)
            and _match(r.workload, workload)
            and _match(r.incident_type, incident_type)
        ):
            return _silence_dict(r)
    return None


# --------------------------------------------------------------------------- autorremediação
_auto_runs: dict[str, list[float]] = {}


def _policy_dict(p: RemediationPolicy) -> dict[str, Any]:
    return {
        "id": p.id,
        "cluster": p.cluster_id,
        "namespace": p.namespace,
        "workload": p.workload,
        "type": p.incident_type,
        "action": p.action,
        "maxPerHour": p.max_per_hour,
        "enabled": p.enabled,
        "createdBy": p.created_by,
    }


async def create_policy(
    *, cluster: str, namespace: str, workload: str, incident_type: str, action: str, max_per_hour: int, created_by: str
) -> dict[str, Any]:
    spec = ACTIONS.get(action)
    if not spec or not spec.auto_eligible:
        allowed = ", ".join(a.id for a in ACTIONS.values() if a.auto_eligible)
        raise InvalidAction(f"só ações de baixo risco podem ser automáticas: {allowed}")
    if not incident_type.strip() or incident_type.strip() == "*":
        raise ValueError("informe o tipo de falha (uma política vale para um tipo específico)")
    row = RemediationPolicy(
        id=str(uuid.uuid4()),
        cluster_id=cluster or "*",
        namespace=namespace or "*",
        workload=workload or "*",
        incident_type=incident_type.strip(),
        action=action,
        max_per_hour=max(1, min(int(max_per_hour), 10)),
        created_by=created_by,
    )
    async with db.session() as s:
        s.add(row)
        await s.commit()
    return _policy_dict(row)


async def list_policies() -> list[dict[str, Any]]:
    async with db.session() as s:
        return [_policy_dict(p) for p in (await s.scalars(select(RemediationPolicy))).all()]


async def set_policy_enabled(policy_id: str, enabled: bool) -> bool:
    async with db.session() as s:
        row = await s.get(RemediationPolicy, policy_id)
        if not row:
            return False
        row.enabled = enabled
        await s.commit()
    return True


async def delete_policy(policy_id: str) -> bool:
    async with db.session() as s:
        res = await s.execute(delete(RemediationPolicy).where(RemediationPolicy.id == policy_id))
        await s.commit()
    return bool(res.rowcount)  # type: ignore[attr-defined]


async def matching_policy(cluster: str, namespace: str, workload: str, incident_type: str, action: str) -> dict | None:
    """Política ativa que libera esta ação agora (respeitando o limite por hora)."""
    async with db.session() as s:
        rows = (
            await s.scalars(
                select(RemediationPolicy).where(
                    RemediationPolicy.enabled,
                    RemediationPolicy.action == action,
                    RemediationPolicy.incident_type == incident_type,
                )
            )
        ).all()
    now = time.monotonic()
    for p in rows:
        if not (_match(p.cluster_id, cluster) and _match(p.namespace, namespace) and _match(p.workload, workload)):
            continue
        runs = [t for t in _auto_runs.get(p.id, []) if now - t < 3600]
        _auto_runs[p.id] = runs
        if len(runs) >= p.max_per_hour:
            continue  # limite atingido: volta a pedir aprovação humana
        runs.append(now)
        return _policy_dict(p)
    return None


# --------------------------------------------------------------------------- plantão
async def add_shift(team_id: str, user_email: str, level: int, starts_at: datetime, ends_at: datetime) -> dict:
    if ends_at <= starts_at:
        raise ValueError("o fim do plantão precisa ser depois do início")
    email = user_email.strip().lower()
    async with db.session() as s:
        if not await s.get(Team, team_id):
            raise LookupError(team_id)
        if not await s.scalar(select(User).where(User.email == email, User.is_active)):
            raise ValueError(f"usuário inexistente ou desativado: {email}")
        row = OnCallShift(
            team_id=team_id, user_email=email, level=1 if level != 2 else 2, starts_at=starts_at, ends_at=ends_at
        )
        s.add(row)
        await s.commit()
        return {
            "id": row.id,
            "teamId": team_id,
            "user": email,
            "level": row.level,
            "startsAt": _iso(starts_at),
            "endsAt": _iso(ends_at),
        }


async def list_shifts(team_id: str | None = None) -> list[dict[str, Any]]:
    stmt = (
        select(OnCallShift, Team.name).join(Team).where(OnCallShift.ends_at > utcnow()).order_by(OnCallShift.starts_at)
    )
    if team_id:
        stmt = stmt.where(OnCallShift.team_id == team_id)
    async with db.session() as s:
        rows = (await s.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "teamId": r.team_id,
            "team": name,
            "user": r.user_email,
            "level": r.level,
            "startsAt": _iso(r.starts_at),
            "endsAt": _iso(r.ends_at),
        }
        for r, name in rows
    ]


async def delete_shift(shift_id: int) -> bool:
    async with db.session() as s:
        res = await s.execute(delete(OnCallShift).where(OnCallShift.id == shift_id))
        await s.commit()
    return bool(res.rowcount)  # type: ignore[attr-defined]


async def responders(cluster: str, namespace: str) -> dict[int, list[str]]:
    """Quem está de plantão agora para este (cluster, namespace), por nível: {1: [...], 2: [...]}."""
    now = utcnow()
    async with db.session() as s:
        scopes = (await s.execute(select(TeamScope.team_id, TeamScope.cluster_id, TeamScope.namespace))).all()
        teams = {t for t, c, n in scopes if _match(c, cluster) and _match(n, namespace)}
        if not teams:
            return {}
        shifts = (
            await s.scalars(
                select(OnCallShift).where(
                    OnCallShift.team_id.in_(teams), OnCallShift.starts_at <= now, OnCallShift.ends_at > now
                )
            )
        ).all()
    out: dict[int, list[str]] = {}
    for sh in shifts:
        out.setdefault(sh.level, []).append(sh.user_email)
    return {k: sorted(set(v)) for k, v in out.items()}


async def admins() -> list[str]:
    async with db.session() as s:
        return sorted((await s.scalars(select(User.email).where(User.role == "admin", User.is_active))).all())


async def team_members_for_scope(cluster: str, namespace: str) -> list[str]:
    async with db.session() as s:
        rows = (
            await s.execute(
                select(TeamScope.cluster_id, TeamScope.namespace, User.email)
                .join(TeamMember, TeamMember.team_id == TeamScope.team_id)
                .join(User, User.id == TeamMember.user_id)
                .where(User.is_active)
            )
        ).all()
    return sorted({e for c, n, e in rows if _match(c, cluster) and _match(n, namespace)})
