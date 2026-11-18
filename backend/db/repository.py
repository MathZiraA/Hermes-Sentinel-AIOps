"""Acesso a dados: incidentes, linha do tempo, clusters, auditoria e relatórios."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, false, func, or_, select

from db import engine as db
from db.models import AuditEntry, Cluster, IncidentEvent, IncidentRow, utcnow
from domain.lifecycle import OPEN, normalize_status
from schemas.events import Incident

GENESIS = "0" * 64


def _dt(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite devolve datas sem fuso; tudo aqui é UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


# --------------------------------------------------------------------------- clusters
async def ensure_cluster(cluster_id: str, name: str, context: str | None = None) -> None:
    async with db.session() as s:
        row = await s.get(Cluster, cluster_id)
        if row is None:
            s.add(Cluster(id=cluster_id, name=name, context=context, last_seen_at=utcnow()))
        else:
            row.context, row.last_seen_at = context or row.context, utcnow()
        await s.commit()


async def list_clusters() -> list[dict[str, Any]]:
    async with db.session() as s:
        clusters = (await s.scalars(select(Cluster).order_by(Cluster.name))).all()
        counts = dict(
            (
                await s.execute(
                    select(IncidentRow.cluster_id, func.count())
                    .where(IncidentRow.status.in_(OPEN))
                    .group_by(IncidentRow.cluster_id)
                )
            ).all()
        )
    return [
        {
            "id": c.id,
            "name": c.name,
            "context": c.context,
            "openIncidents": counts.get(c.id, 0),
            "lastSeenAt": _aware(c.last_seen_at).isoformat() if c.last_seen_at else None,
        }
        for c in clusters
    ]


# --------------------------------------------------------------------------- incidentes
def _row_values(inc: Incident) -> dict[str, Any]:
    return {
        "cluster_id": inc.cluster,
        "type": inc.type,
        "sev": inc.sev,
        "status": inc.status,
        "namespace": inc.namespace or "",
        "workload": inc.deployment or inc.pod,
        "resource_kind": inc.resourceKind,
        "simulated": inc.simulated,
        "detected_at": _dt(inc.detectedAt),
        "acknowledged_at": _dt(inc.acknowledgedAt),
        "resolved_at": _dt(inc.resolvedAt),
        "data": inc.model_dump(mode="json"),
    }


async def save_incident(inc: Incident) -> None:
    values = _row_values(inc)
    async with db.session() as s:
        row = await s.get(IncidentRow, inc.id)
        if row is None:
            s.add(IncidentRow(id=inc.id, **values))
        else:
            for k, v in values.items():
                setattr(row, k, v)
            row.updated_at = utcnow()
        await s.commit()


async def add_event(incident_id: str, text: str, actor: str = "sistema", kind: str = "note") -> None:
    async with db.session() as s:
        s.add(IncidentEvent(incident_id=incident_id, text=text[:4000], actor=actor[:120], kind=kind))
        await s.commit()


def _load(row: IncidentRow) -> Incident:
    data = dict(row.data)
    data["status"] = normalize_status(data.get("status", row.status))
    return Incident.model_validate(data)


async def get_incident(incident_id: str) -> tuple[Incident, list[dict[str, Any]]] | None:
    async with db.session() as s:
        row = await s.get(IncidentRow, incident_id)
        if row is None:
            return None
        events = (
            await s.scalars(
                select(IncidentEvent).where(IncidentEvent.incident_id == incident_id).order_by(IncidentEvent.id)
            )
        ).all()
    timeline = [
        {"ts": _aware(e.ts).isoformat(), "actor": e.actor, "kind": e.kind, "text": e.text}  # type: ignore[union-attr]
        for e in events
    ]
    return _load(row), timeline


async def list_incidents(
    *,
    status: list[str] | None = None,
    sev: list[str] | None = None,
    cluster: str | None = None,
    namespaces: list[str] | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
    scopes: list[tuple[str, str]] | None = None,
) -> tuple[list[Incident], int]:
    """`scopes`: pares (cluster, namespace) visíveis, com "*" como curinga. None = sem restrição."""
    stmt = select(IncidentRow)
    if scopes is not None:
        conds = []
        for c, n in scopes:
            parts = []
            if c != "*":
                parts.append(IncidentRow.cluster_id == c)
            if n != "*":
                parts.append(IncidentRow.namespace == n)
            conds.append(and_(*parts) if parts else IncidentRow.id.isnot(None))
        stmt = stmt.where(or_(*conds) if conds else false())
    if status:
        stmt = stmt.where(IncidentRow.status.in_(status))
    if sev:
        stmt = stmt.where(IncidentRow.sev.in_(sev))
    if cluster:
        stmt = stmt.where(IncidentRow.cluster_id == cluster)
    if namespaces is not None:
        stmt = stmt.where(IncidentRow.namespace.in_(namespaces))
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(
            func.lower(IncidentRow.workload).like(like)
            | func.lower(IncidentRow.type).like(like)
            | func.lower(IncidentRow.id).like(like)
        )
    async with db.session() as s:
        total = await s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            await s.scalars(stmt.order_by(IncidentRow.detected_at.desc()).limit(min(limit, 200)).offset(offset))
        ).all()
    return [_load(r) for r in rows], total


async def open_incidents() -> list[Incident]:
    items, _ = await list_incidents(status=sorted(OPEN), limit=200)
    return items


# --------------------------------------------------------------------------- auditoria (cadeia de hash)
_audit_lock = asyncio.Lock()


def _canonical(entry: dict[str, Any]) -> str:
    return json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def entry_hash(
    prev_hash: str, ts: datetime, actor: str, action: str, target: str, ip: str | None, details: dict
) -> str:
    body = _canonical(
        {
            "prev": prev_hash,
            "ts": _aware(ts).isoformat(),  # type: ignore[union-attr]
            "actor": actor,
            "action": action,
            "target": target,
            "ip": ip,
            "details": details,
        }
    )
    return hashlib.sha256(body.encode()).hexdigest()


async def audit(
    actor: str, action: str, target: str = "", details: dict[str, Any] | None = None, ip: str | None = None
) -> str:
    """Grava uma entrada encadeada. Escritor único por processo (lock); devolve o hash."""
    details = details or {}
    async with _audit_lock, db.session() as s:
        prev = await s.scalar(select(AuditEntry.hash).order_by(AuditEntry.id.desc()).limit(1)) or GENESIS
        ts = utcnow()
        h = entry_hash(prev, ts, actor, action, target, ip, details)
        s.add(
            AuditEntry(
                ts=ts,
                actor=actor[:120],
                action=action[:80],
                target=target[:255],
                ip=ip,
                details=details,
                prev_hash=prev,
                hash=h,
            )
        )
        await s.commit()
    return h


def _audit_dict(e: AuditEntry) -> dict[str, Any]:
    return {
        "id": e.id,
        "ts": _aware(e.ts).isoformat(),  # type: ignore[union-attr]
        "actor": e.actor,
        "action": e.action,
        "target": e.target,
        "ip": e.ip,
        "details": e.details,
        "prevHash": e.prev_hash,
        "hash": e.hash,
    }


async def list_audit(limit: int = 100, offset: int = 0, actor: str | None = None) -> tuple[list[dict], int]:
    stmt = select(AuditEntry)
    if actor:
        stmt = stmt.where(AuditEntry.actor == actor)
    async with db.session() as s:
        total = await s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (await s.scalars(stmt.order_by(AuditEntry.id.desc()).limit(min(limit, 1000)).offset(offset))).all()
    return [_audit_dict(r) for r in rows], total


async def verify_audit() -> dict[str, Any]:
    """Recalcula a cadeia inteira. Qualquer linha alterada ou removida quebra a verificação."""
    async with db.session() as s:
        rows = (await s.scalars(select(AuditEntry).order_by(AuditEntry.id))).all()
    prev = GENESIS
    for r in rows:
        expected = entry_hash(prev, r.ts, r.actor, r.action, r.target, r.ip, r.details)
        if r.prev_hash != prev or r.hash != expected:
            return {"ok": False, "entries": len(rows), "brokenAt": r.id}
        prev = r.hash
    return {"ok": True, "entries": len(rows), "head": prev}


async def export_audit(fmt: str = "json") -> str:
    entries, _ = await list_audit(limit=1_000_000)
    entries.reverse()
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(
            buf, fieldnames=["id", "ts", "actor", "action", "target", "ip", "details", "prevHash", "hash"]
        )
        w.writeheader()
        for e in entries:
            w.writerow({**e, "details": _canonical(e["details"])})
        return buf.getvalue()
    return json.dumps(entries, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- relatórios
async def summary(
    days: int = 30, cluster: str | None = None, scopes: list[tuple[str, str]] | None = None
) -> dict[str, Any]:
    """MTTA/MTTR, volume por severidade, status e serviço, e taxa de aprovação."""
    since = utcnow() - timedelta(days=days)
    items, _ = await list_incidents(cluster=cluster, scopes=scopes, limit=200)
    items = [i for i in items if (_dt(i.detectedAt) or since) >= since and not i.simulated]

    def minutes(a: str | None, b: str | None) -> float | None:
        da, dbb = _dt(a), _dt(b)
        return round((dbb - da).total_seconds() / 60, 1) if da and dbb else None

    mtta = [m for i in items if (m := minutes(i.detectedAt, i.acknowledgedAt)) is not None]
    mttr = [m for i in items if (m := minutes(i.detectedAt, i.resolvedAt)) is not None]
    by: dict[str, dict[str, int]] = {"sev": {}, "status": {}, "service": {}, "type": {}}
    decisions = {"approved": 0, "rejected": 0}
    for i in items:
        for key, value in (("sev", i.sev), ("status", i.status), ("service", i.deployment or i.pod), ("type", i.type)):
            by[key][value] = by[key].get(value, 0) + 1
        if i.decision in decisions:
            decisions[i.decision] += 1
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None  # noqa: E731
    return {
        "periodDays": days,
        "incidents": len(items),
        "open": sum(1 for i in items if i.status in OPEN),
        "mttaMinutes": avg(mtta),
        "mttrMinutes": avg(mttr),
        "bySev": by["sev"],
        "byStatus": by["status"],
        "byService": dict(sorted(by["service"].items(), key=lambda kv: -kv[1])[:10]),
        "byType": dict(sorted(by["type"].items(), key=lambda kv: -kv[1])[:10]),
        "decisions": decisions,
    }
