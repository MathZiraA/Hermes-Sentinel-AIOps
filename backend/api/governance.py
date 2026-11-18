"""Auditoria, relatórios e clusters."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from db import repository as repo

router = APIRouter(prefix="/api", tags=["governança"])


@router.get("/audit", summary="Trilha de auditoria (mais recentes primeiro)")
async def audit_log(
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    actor: str | None = None,
) -> dict[str, Any]:
    items, total = await repo.list_audit(limit=limit, offset=offset, actor=actor)
    return {"total": total, "items": items}


@router.get("/audit/verify", summary="Verifica a integridade da cadeia de hashes")
async def audit_verify() -> dict[str, Any]:
    return await repo.verify_audit()


@router.get("/audit/export", summary="Exporta a auditoria completa", response_class=PlainTextResponse)
async def audit_export(format: Literal["json", "csv"] = "json") -> PlainTextResponse:
    body = await repo.export_audit(format)
    media = "text/csv" if format == "csv" else "application/json"
    return PlainTextResponse(
        body, media_type=media, headers={"Content-Disposition": f'attachment; filename="audit.{format}"'}
    )


@router.get("/reports/summary", summary="MTTA, MTTR e volume de incidentes")
async def report_summary(days: Annotated[int, Query(ge=1, le=365)] = 30, cluster: str | None = None) -> dict[str, Any]:
    return await repo.summary(days=days, cluster=cluster)


@router.get("/clusters", summary="Clusters conhecidos")
async def clusters() -> list[dict[str, Any]]:
    return await repo.list_clusters()
