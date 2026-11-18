"""Operação: janelas de manutenção (silêncios), autorremediação e plantão."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.deps import client_ip, require
from db import operations as ops
from db import repository as repo
from domain.actions import ACTIONS, InvalidAction
from domain.permissions import Principal

router = APIRouter(prefix="/api", tags=["operação"])
Reader = Annotated[Principal, Depends(require("incidents:read"))]
SilenceAdmin = Annotated[Principal, Depends(require("silences:manage"))]
PolicyAdmin = Annotated[Principal, Depends(require("settings:manage"))]
TeamsAdmin = Annotated[Principal, Depends(require("teams:manage"))]


class SilenceIn(BaseModel):
    cluster: str = Field(default="*", max_length=63)
    namespace: str = Field(default="*", max_length=63)
    workload: str = Field(default="*", max_length=253)
    type: str = Field(default="*", max_length=80)
    startsAt: datetime
    endsAt: datetime
    reason: str = Field(max_length=500)


class PolicyIn(BaseModel):
    cluster: str = Field(default="*", max_length=63)
    namespace: str = Field(default="*", max_length=63)
    workload: str = Field(default="*", max_length=253)
    type: str = Field(max_length=80)
    action: str
    maxPerHour: int = Field(default=2, ge=1, le=10)


class PolicyPatch(BaseModel):
    enabled: bool


class ShiftIn(BaseModel):
    teamId: str
    user: str = Field(max_length=254)
    level: int = Field(default=1, ge=1, le=2)
    startsAt: datetime
    endsAt: datetime


# --------------------------------------------------------------------------- catálogo
@router.get("/actions", summary="Catálogo de ações de correção")
async def actions(_: Reader) -> list[dict[str, Any]]:
    return [
        {
            "id": a.id,
            "label": a.label,
            "risk": a.risk,
            "targets": list(a.targets),
            "autoEligible": a.auto_eligible,
            "description": a.description,
        }
        for a in ACTIONS.values()
    ]


# --------------------------------------------------------------------------- silêncios
@router.get("/silences", summary="Janelas de manutenção ativas e futuras")
async def list_silences(_: Reader, expired: bool = False) -> list[dict[str, Any]]:
    return await ops.list_silences(include_expired=expired)


@router.post("/silences", status_code=201, summary="Criar janela de manutenção")
async def create_silence(body: SilenceIn, request: Request, who: SilenceAdmin) -> dict[str, Any]:
    try:
        row = await ops.create_silence(
            cluster=body.cluster,
            namespace=body.namespace,
            workload=body.workload,
            incident_type=body.type,
            starts_at=body.startsAt,
            ends_at=body.endsAt,
            reason=body.reason,
            created_by=who.email,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await repo.audit(who.email, "silence.create", row["id"], body.model_dump(mode="json"), client_ip(request))
    return row


@router.delete("/silences/{silence_id}", summary="Encerrar janela de manutenção agora")
async def end_silence(silence_id: str, request: Request, who: SilenceAdmin) -> dict[str, bool]:
    if not await ops.expire_silence(silence_id):
        raise HTTPException(404, "silêncio não encontrado")
    await repo.audit(who.email, "silence.end", silence_id, {}, client_ip(request))
    return {"ok": True}


# --------------------------------------------------------------------------- autorremediação
@router.get("/policies", summary="Políticas de autorremediação")
async def list_policies(_: Reader) -> list[dict[str, Any]]:
    return await ops.list_policies()


@router.post("/policies", status_code=201, summary="Liberar uma ação de baixo risco sem aprovação")
async def create_policy(body: PolicyIn, request: Request, admin: PolicyAdmin) -> dict[str, Any]:
    try:
        row = await ops.create_policy(
            cluster=body.cluster,
            namespace=body.namespace,
            workload=body.workload,
            incident_type=body.type,
            action=body.action,
            max_per_hour=body.maxPerHour,
            created_by=admin.email,
        )
    except (InvalidAction, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    await repo.audit(admin.email, "policy.create", row["id"], body.model_dump(), client_ip(request))
    return row


@router.patch("/policies/{policy_id}", summary="Ligar ou desligar uma política")
async def toggle_policy(policy_id: str, body: PolicyPatch, request: Request, admin: PolicyAdmin) -> dict[str, bool]:
    if not await ops.set_policy_enabled(policy_id, body.enabled):
        raise HTTPException(404, "política não encontrada")
    await repo.audit(admin.email, "policy.update", policy_id, {"enabled": body.enabled}, client_ip(request))
    return {"ok": True}


@router.delete("/policies/{policy_id}", summary="Apagar uma política")
async def remove_policy(policy_id: str, request: Request, admin: PolicyAdmin) -> dict[str, bool]:
    if not await ops.delete_policy(policy_id):
        raise HTTPException(404, "política não encontrada")
    await repo.audit(admin.email, "policy.delete", policy_id, {}, client_ip(request))
    return {"ok": True}


# --------------------------------------------------------------------------- plantão
@router.get("/oncall", summary="Escala de plantão (atual e futura)")
async def list_oncall(_: Reader, team: str | None = None) -> list[dict[str, Any]]:
    return await ops.list_shifts(team)


@router.post("/oncall", status_code=201, summary="Adicionar turno de plantão")
async def add_shift(body: ShiftIn, request: Request, admin: TeamsAdmin) -> dict[str, Any]:
    try:
        row = await ops.add_shift(body.teamId, body.user, body.level, body.startsAt, body.endsAt)
    except LookupError as exc:
        raise HTTPException(404, "time não encontrado") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await repo.audit(admin.email, "oncall.add", body.teamId, body.model_dump(mode="json"), client_ip(request))
    return row


@router.delete("/oncall/{shift_id}", summary="Remover turno de plantão")
async def delete_shift(shift_id: int, request: Request, admin: TeamsAdmin) -> dict[str, bool]:
    if not await ops.delete_shift(shift_id):
        raise HTTPException(404, "turno não encontrado")
    await repo.audit(admin.email, "oncall.delete", str(shift_id), {}, client_ip(request))
    return {"ok": True}
