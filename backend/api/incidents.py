"""Rotas de incidentes: lista, detalhe, reconhecer, aprovar e rejeitar."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from agents.orchestrator import orchestrator
from api.deps import Actor, actor_for, require
from config import settings
from db import repository as repo
from domain.lifecycle import STATUS_LABEL, SlaPolicy
from domain.permissions import Principal
from schemas.events import DecisionRequest, Incident

router = APIRouter(prefix="/api", tags=["incidentes"])
sla = SlaPolicy(settings.sla_ack_minutes, settings.sla_resolve_minutes)


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def summary_of(inc: Incident) -> dict[str, Any]:
    """Visão de lista: sem logs, com rótulo do status e estado do SLA."""
    data = inc.model_dump(exclude={"logs", "events", "memory"})
    detected = _parse(inc.detectedAt) or datetime.now(UTC)
    data["statusLabel"] = STATUS_LABEL.get(inc.status, inc.status)
    data["sla"] = sla.evaluate(inc.sev, detected, _parse(inc.acknowledgedAt), _parse(inc.resolvedAt), datetime.now(UTC))
    return data


Reader = Annotated[Principal, Depends(require("incidents:read"))]


def scope_filter(p: Principal) -> list[tuple[str, str]] | None:
    """None = vê tudo; senão, os pares (cluster, namespace) dos times do usuário."""
    return None if p.unrestricted else [(s.cluster, s.namespace) for s in p.scopes]


def _ensure_visible(p: Principal, inc: Incident) -> None:
    if not p.sees(inc.cluster, inc.namespace):
        raise HTTPException(404, "incidente não encontrado")  # 404, não 403: não revela que existe


def _live(inc_id: str) -> Incident | None:
    """O orquestrador tem a versão mais nova de um incidente em andamento."""
    return orchestrator.incidents.get(inc_id)


@router.get("/incidents", summary="Lista incidentes com filtros")
async def list_incidents(
    status: Annotated[list[str] | None, Query()] = None,
    sev: Annotated[list[str] | None, Query()] = None,
    cluster: str | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    *,
    principal: Reader,
) -> dict[str, Any]:
    items, total = await repo.list_incidents(
        status=status, sev=sev, cluster=cluster, query=q, limit=limit, offset=offset, scopes=scope_filter(principal)
    )
    return {"total": total, "items": [summary_of(_live(i.id) or i) for i in items]}


@router.get("/incidents/{incident_id}", summary="Detalhe do incidente com linha do tempo")
async def get_incident(incident_id: str, principal: Reader) -> dict[str, Any]:
    found = await repo.get_incident(incident_id)
    if not found:
        raise HTTPException(404, "incidente não encontrado")
    inc, timeline = found
    inc = _live(incident_id) or inc
    _ensure_visible(principal, inc)
    return {**summary_of(inc), "logs": inc.logs, "events": inc.events, "memory": inc.memory, "timeline": timeline}


@router.post("/incidents/{incident_id}/acknowledge", summary="Assumir o incidente")
async def acknowledge(incident_id: str, actor: Annotated[Actor, Depends(actor_for("incidents:ack"))]) -> dict[str, Any]:
    live = _live(incident_id)
    if live:
        _ensure_visible(actor.principal, live)
    try:
        inc = await orchestrator.acknowledge(incident_id, actor.name)
    except KeyError as exc:
        raise HTTPException(404, "incidente inexistente ou já encerrado") from exc
    await repo.audit(actor.name, "incident.acknowledge", incident_id, {"status": inc.status}, actor.ip)
    return summary_of(inc)


async def _decide(incident_id: str, approve: bool, body: DecisionRequest | None, actor: Actor) -> dict[str, Any]:
    reason = (body or DecisionRequest()).motivo
    if not approve and not reason.strip():
        raise HTTPException(422, "informe o motivo da rejeição: ele vira uma lição para o time")
    live = _live(incident_id)
    if live:
        _ensure_visible(actor.principal, live)
    try:
        if approve:
            inc = await orchestrator.approve(incident_id, reason, actor=actor.name)
        else:
            inc = await orchestrator.reject(incident_id, reason, actor=actor.name)
    except KeyError as exc:
        raise HTTPException(404, "incidente inexistente ou sem aprovação pendente") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    await repo.audit(
        actor.name,
        "remediation.approve" if approve else "remediation.reject",
        incident_id,
        {"command": inc.approval.command if inc.approval else None, "motivo": reason or None, "sev": inc.sev},
        actor.ip,
    )
    return {"incidentId": inc.id, "status": inc.status, "command": inc.approval.command if inc.approval else None}


@router.post("/agents/approve/{incident_id}", summary="Aprovar a correção proposta")
async def approve(
    incident_id: str,
    actor: Annotated[Actor, Depends(actor_for("incidents:decide"))],
    body: DecisionRequest | None = None,
) -> dict[str, Any]:
    return await _decide(incident_id, True, body, actor)


@router.post("/agents/reject/{incident_id}", summary="Rejeitar a correção proposta")
async def reject(
    incident_id: str,
    actor: Annotated[Actor, Depends(actor_for("incidents:decide"))],
    body: DecisionRequest | None = None,
) -> dict[str, Any]:
    return await _decide(incident_id, False, body, actor)
