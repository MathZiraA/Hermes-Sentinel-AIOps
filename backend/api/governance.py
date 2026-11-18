"""Auditoria, relatórios e clusters."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from api.deps import require
from api.incidents import scope_filter
from db import repository as repo
from domain.permissions import Principal

Auditor = Annotated[Principal, Depends(require("audit:read"))]
Reporter = Annotated[Principal, Depends(require("reports:read"))]
ClusterReader = Annotated[Principal, Depends(require("clusters:read"))]

router = APIRouter(prefix="/api", tags=["governança"])


@router.get("/audit", summary="Trilha de auditoria (mais recentes primeiro)")
async def audit_log(
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    actor: str | None = None,
    *,
    _: Auditor,
) -> dict[str, Any]:
    items, total = await repo.list_audit(limit=limit, offset=offset, actor=actor)
    return {"total": total, "items": items}


@router.get("/audit/verify", summary="Verifica a integridade da cadeia de hashes")
async def audit_verify(_: Auditor) -> dict[str, Any]:
    return await repo.verify_audit()


@router.get("/audit/export", summary="Exporta a auditoria completa", response_class=PlainTextResponse)
async def audit_export(_: Auditor, format: Literal["json", "csv"] = "json") -> PlainTextResponse:
    body = await repo.export_audit(format)
    media = "text/csv" if format == "csv" else "application/json"
    return PlainTextResponse(
        body, media_type=media, headers={"Content-Disposition": f'attachment; filename="audit.{format}"'}
    )


@router.get("/reports/summary", summary="MTTA, MTTR e volume de incidentes")
async def report_summary(
    principal: Reporter, days: Annotated[int, Query(ge=1, le=365)] = 30, cluster: str | None = None
) -> dict[str, Any]:
    return await repo.summary(days=days, cluster=cluster, scopes=scope_filter(principal))


@router.get("/clusters", summary="Clusters conhecidos")
async def clusters(principal: ClusterReader) -> list[dict[str, Any]]:
    visible = await repo.list_clusters()
    if principal.unrestricted:
        return visible
    allowed = {s.cluster for s in principal.scopes}
    return [c for c in visible if "*" in allowed or c["id"] in allowed]


@router.get("/ai/usage", summary="Consumo de IA: chamadas, tokens, custo estimado e orçamento")
async def ai_usage(_: Reporter, days: Annotated[int, Query(ge=1, le=90)] = 30) -> dict[str, Any]:
    from db import ai

    return await ai.usage(days)
