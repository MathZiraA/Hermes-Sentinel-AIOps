"""Integrações: estado e entrada de alertas do Zabbix (webhook)."""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from agents.orchestrator import orchestrator
from api.deps import client_ip, require
from config import settings
from db import repository as repo
from domain.permissions import Principal
from integrations import observability

router = APIRouter(prefix="/api/integrations", tags=["integrações"])

ZABBIX_SEV = {
    "disaster": "SEV1",
    "high": "SEV2",
    "average": "SEV3",
    "warning": "SEV4",
    "information": "SEV4",
    "not classified": "SEV4",
    "5": "SEV1",
    "4": "SEV2",
    "3": "SEV3",
    "2": "SEV4",
    "1": "SEV4",
    "0": "SEV4",
}


class ZabbixEvent(BaseModel):
    """Corpo enviado pelo media type webhook do Zabbix (ver docs/operations/integrations.md)."""

    event_id: str = Field(max_length=64)
    status: str = Field(default="PROBLEM", max_length=16)  # PROBLEM | RESOLVED
    host: str = Field(max_length=253)
    trigger: str = Field(max_length=255)
    severity: str = Field(default="Average", max_length=32)
    message: str = Field(default="", max_length=4000)
    namespace: str = Field(default="", max_length=63)  # tag opcional do host/trigger
    workload: str = Field(default="", max_length=253)
    event_url: str = Field(default="", max_length=500)


@router.get("", summary="Estado das integrações")
async def integrations_status(_: Annotated[Principal, Depends(require("health:read"))]) -> dict[str, Any]:
    return observability.status()


@router.post("/zabbix", status_code=202, summary="Webhook do Zabbix: alertas viram incidentes")
async def zabbix_webhook(
    body: ZabbixEvent, request: Request, authorization: Annotated[str, Header()] = ""
) -> dict[str, Any]:
    token = settings.zabbix_webhook_token
    if not token or not hmac.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
        raise HTTPException(401, "token do webhook inválido")
    sev = ZABBIX_SEV.get(body.severity.strip().lower(), "SEV3")
    inc = await orchestrator.ingest_zabbix(body.model_dump(), sev)
    await repo.audit(
        "zabbix",
        "integration.zabbix_event",
        inc.id if inc else body.event_id,
        {"status": body.status, "trigger": body.trigger, "host": body.host},
        client_ip(request),
    )
    return {"incidentId": inc.id if inc else None, "status": inc.status if inc else "ignorado"}
