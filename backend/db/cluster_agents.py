"""Clusters remotos: token do agente e fila de comandos aprovados."""

from __future__ import annotations

import hmac
import re
import uuid
from typing import Any

from sqlalchemy import select

from db import engine as db
from db.models import AgentCommand, Cluster, utcnow
from identity import crypto

CLUSTER_ID = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")


async def register_cluster(cluster_id: str, name: str) -> str:
    """Cria (ou recria o token de) um cluster remoto. Devolve o token UMA vez; só o hash fica no banco."""
    if not CLUSTER_ID.match(cluster_id):
        raise ValueError("id do cluster inválido (letras minúsculas, números e hífen)")
    token = "sca_" + crypto.new_token()
    async with db.session() as s:
        row = await s.get(Cluster, cluster_id)
        if row is None:
            row = Cluster(id=cluster_id, name=name.strip() or cluster_id)
            s.add(row)
        row.agent_token_hash = crypto.token_id(token)
        await s.commit()
    return token


async def cluster_for_token(token: str) -> str | None:
    if not token.startswith("sca_"):
        return None
    wanted = crypto.token_id(token)
    async with db.session() as s:
        rows = (await s.scalars(select(Cluster).where(Cluster.agent_token_hash.isnot(None)))).all()
    for r in rows:
        if hmac.compare_digest(r.agent_token_hash or "", wanted):
            return r.id
    return None


async def heartbeat(cluster_id: str, version: str) -> None:
    async with db.session() as s:
        row = await s.get(Cluster, cluster_id)
        if row:
            row.last_seen_at, row.agent_version = utcnow(), version[:40]
            await s.commit()


async def enqueue(
    cluster_id: str,
    incident_id: str,
    action: str,
    params: dict[str, Any],
    *,
    namespace: str,
    workload: str,
    pod: str,
    resource_kind: str,
) -> str:
    cmd = AgentCommand(
        id=str(uuid.uuid4()),
        cluster_id=cluster_id,
        incident_id=incident_id,
        action=action,
        params=params,
        namespace=namespace,
        workload=workload,
        pod=pod,
        resource_kind=resource_kind,
    )
    async with db.session() as s:
        s.add(cmd)
        await s.commit()
    return cmd.id


async def take_pending(cluster_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Entrega os comandos pendentes e os marca como enviados (o agente responde pelo resultado)."""
    async with db.session() as s:
        rows = (
            await s.scalars(
                select(AgentCommand)
                .where(AgentCommand.cluster_id == cluster_id, AgentCommand.status == "pending")
                .order_by(AgentCommand.created_at)
                .limit(limit)
            )
        ).all()
        out = []
        for r in rows:
            r.status = "sent"
            out.append(
                {
                    "id": r.id,
                    "incidentId": r.incident_id,
                    "action": r.action,
                    "params": r.params,
                    "namespace": r.namespace,
                    "workload": r.workload,
                    "pod": r.pod,
                    "kind": r.resource_kind,
                }
            )
        await s.commit()
    return out


async def complete(cluster_id: str, command_id: str, result: dict[str, Any]) -> AgentCommand | None:
    async with db.session() as s:
        row = await s.get(AgentCommand, command_id)
        if not row or row.cluster_id != cluster_id or row.status not in ("sent", "pending"):
            return None
        row.status = "done" if result.get("ok") else "error"
        row.result = result
        await s.commit()
        return row
