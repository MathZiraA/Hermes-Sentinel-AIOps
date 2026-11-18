"""Dados das telas: estado do cluster e Hermes Brain (busca, notas e grafo)."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import require
from config import settings
from domain.permissions import Principal
from integrations import brain, brain_index
from k8s.client import K8sUnavailable, k8s
from k8s.watcher import watcher

router = APIRouter(prefix="/api", tags=["telas"])
ClusterReader = Annotated[Principal, Depends(require("clusters:read"))]
BrainReader = Annotated[Principal, Depends(require("brain:read"))]


@router.get("/clusters/{cluster_id}/status", summary="Nós, workloads e pods do cluster")
async def cluster_status(cluster_id: str, principal: ClusterReader) -> dict[str, Any]:
    if cluster_id != settings.cluster_id:
        raise HTTPException(404, "cluster não conectado a esta instância (multicluster: Fase 7)")
    namespaces = list(settings.k8s_namespaces) or ["default"]
    if not principal.unrestricted:
        allowed = {s.namespace for s in principal.scopes if s.cluster in ("*", cluster_id)}
        namespaces = namespaces if "*" in allowed else [n for n in namespaces if n in allowed]
    try:
        data = await asyncio.to_thread(k8s.cluster_status, namespaces)
    except K8sUnavailable as exc:
        raise HTTPException(503, f"cluster indisponível: {exc}") from exc
    except Exception as exc:
        raise HTTPException(503, f"cluster indisponível: {type(exc).__name__}") from exc
    return {**data, "namespaces": namespaces, "watcher": watcher.status, "lastSweep": watcher.last_sweep}


@router.get("/brain/graph", summary="Grafo do Hermes Brain (notas e wikilinks)")
async def brain_graph(_: BrainReader) -> dict[str, Any]:
    return await asyncio.to_thread(brain.graph)


@router.get("/brain/search", summary="Busca no Hermes Brain")
async def brain_search(
    _: BrainReader, q: Annotated[str, Query(min_length=2, max_length=200)], limit: int = 10
) -> list[dict[str, Any]]:
    return await brain_index.search(q, max(1, min(limit, 30)))


@router.get("/brain/notes/{name}", summary="Uma nota do Hermes Brain")
async def brain_note(name: str, _: BrainReader) -> dict[str, str]:
    try:
        folder, text = await asyncio.to_thread(brain.read_note, name)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "nota não encontrada") from exc
    return {"name": name, "folder": folder, "markdown": text}
