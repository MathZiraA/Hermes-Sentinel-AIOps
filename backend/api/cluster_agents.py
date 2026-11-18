"""Multicluster: o agente de cada cluster remoto envia sinais e executa as correções aprovadas.

O agente só faz conexões de SAÍDA para a central (nada exposto no cluster remoto), autenticado por um token
próprio do cluster. A central nunca recebe kubeconfig de clusters remotos.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from agents.orchestrator import orchestrator
from api.deps import client_ip, require
from db import cluster_agents
from db import repository as repo
from domain.permissions import Principal

router = APIRouter(tags=["multicluster"])


class NewCluster(BaseModel):
    id: str = Field(max_length=63)
    name: str = Field(max_length=120)


class Signal(BaseModel):
    type: str = Field(max_length=80)
    namespace: str = Field(default="", max_length=63)
    pod: str = Field(max_length=253)
    container: str = Field(default="", max_length=253)
    reason: str = Field(default="", max_length=500)
    kind: str = Field(default="Pod", max_length=63)
    severity: str = Field(default="alta", max_length=16)
    owner: str = Field(default="", max_length=253)
    logs: str = Field(default="", max_length=20000)
    events: str = Field(default="", max_length=20000)
    rollout: dict | None = None


class Heartbeat(BaseModel):
    version: str = Field(default="?", max_length=40)


class CommandResult(BaseModel):
    ok: bool
    result: str = Field(default="", max_length=2000)
    error: str = Field(default="", max_length=2000)
    healthy: bool = False
    detail: str = Field(default="", max_length=500)


async def agent_cluster(authorization: Annotated[str, Header()] = "") -> str:
    token = authorization.removeprefix("Bearer ").strip()
    cluster = await cluster_agents.cluster_for_token(token) if token else None
    if not cluster:
        raise HTTPException(401, "token de agente inválido")
    return cluster


Agent = Annotated[str, Depends(agent_cluster)]


@router.post(
    "/api/admin/clusters",
    status_code=201,
    tags=["administração"],
    summary="Cadastrar cluster remoto (devolve o token do agente UMA vez)",
)
async def register_cluster(
    body: NewCluster, request: Request, admin: Annotated[Principal, Depends(require("settings:manage"))]
) -> dict[str, str]:
    try:
        token = await cluster_agents.register_cluster(body.id, body.name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await repo.audit(admin.email, "cluster.register", body.id, {"name": body.name}, client_ip(request))
    return {"cluster": body.id, "agentToken": token, "aviso": "Guarde agora: o token não é mostrado de novo."}


@router.post("/api/agent/v1/heartbeat", summary="Agente: estou vivo")
async def heartbeat(body: Heartbeat, cluster: Agent) -> dict[str, str]:
    await cluster_agents.heartbeat(cluster, body.version)
    return {"cluster": cluster}


@router.post("/api/agent/v1/signals", status_code=202, summary="Agente: sinais detectados no cluster")
async def signals(body: list[Signal], cluster: Agent) -> dict[str, Any]:
    ids = []
    for sig in body[:50]:
        inc = await orchestrator.ingest_remote(cluster, sig.model_dump())
        ids.append(inc.id if inc else None)
    await cluster_agents.heartbeat(cluster, "?")
    return {"incidents": ids}


@router.get("/api/agent/v1/commands", summary="Agente: correções aprovadas para executar")
async def commands(cluster: Agent) -> list[dict[str, Any]]:
    return await cluster_agents.take_pending(cluster)


@router.post("/api/agent/v1/commands/{command_id}/result", summary="Agente: resultado e verificação")
async def command_result(command_id: str, body: CommandResult, cluster: Agent) -> dict[str, bool]:
    if not await orchestrator.agent_result(cluster, command_id, body.model_dump()):
        raise HTTPException(404, "comando desconhecido ou já concluído")
    await repo.audit(
        f"agente:{cluster}", "remediation.agent_result", command_id, {"ok": body.ok, "healthy": body.healthy}
    )
    return {"ok": True}
