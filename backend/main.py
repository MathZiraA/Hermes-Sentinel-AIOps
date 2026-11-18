"""Hermes Sentinel — backend local (sensor/executor do k8s + orquestração com o Hermes no VPS).

cd backend && .venv/bin/uvicorn main:app --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import Annotated

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

import mcp_server
from agents.orchestrator import orchestrator
from api import admin as admin_api
from api import auth as auth_api
from api import governance as governance_api
from api import incidents as incidents_api
from api import integrations as integrations_api
from api import operations as operations_api
from api import workspace as workspace_api
from api.deps import Actor, actor_for, require, websocket_principal
from config import settings
from core.bus import bus
from db import engine as db_engine
from db import repository as repo
from domain.permissions import Principal
from identity import service as identity
from integrations import observability, obsidian
from integrations.github_itsm import github_configured
from integrations.hermes_client import hermes
from k8s.client import k8s
from k8s.watcher import watcher
from schemas.events import SimulateRequest, now_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sentinel")

HEALTH_INTERVAL = 30  # s — health checks não usam IA (GET /v1/models)


async def _db_health() -> dict:
    try:
        async with db_engine.session() as s:
            await s.execute(text("SELECT 1"))
        kind = settings.database_url.split("+", 1)[0].split(":", 1)[0]
        return {"ok": True, "detail": kind}
    except Exception as exc:
        return {"ok": False, "detail": type(exc).__name__}


async def collect_health() -> dict:
    kube, gateway = await asyncio.gather(asyncio.to_thread(k8s.check), hermes.ping())
    kube["watcher"] = watcher.status
    return {
        "checkedAt": now_iso(),
        "kubernetes": kube,
        "hermesGateway": gateway,
        "obsidian": obsidian.vault_status(),
        "github": {
            "ok": github_configured(),
            "repo": settings.github_repo,
            "detail": settings.github_repo if github_configured() else "GITHUB_TOKEN não definido",
        },
        "ai": {"calls": hermes.calls, "lastError": hermes.last_error},
        "database": await _db_health(),
        "mcp": {
            "ok": bool(settings.mcp_token),
            "port": settings.mcp_port,
            "detail": f"127.0.0.1:{settings.mcp_port}/mcp" if settings.mcp_token else "SENTINEL_MCP_TOKEN não definido",
        },
        "websocketClients": bus.client_count,
        "integrations": observability.status(),
    }


async def health_loop() -> None:
    while True:
        with suppress(Exception):
            await bus.publish_health(await collect_health())
        await asyncio.sleep(HEALTH_INTERVAL)


@asynccontextmanager
async def lifespan(_: FastAPI):
    from integrations import brain

    if settings.auto_migrate:
        await db_engine.migrate()
    kube = await asyncio.to_thread(k8s.check)
    await repo.ensure_cluster(
        settings.cluster_id, settings.cluster_name or kube.get("context") or settings.cluster_id, kube.get("context")
    )
    from integrations import jira

    jira.register()
    await identity.bootstrap_admin()
    if settings.auth_enabled and await identity.count_users() == 0:
        log.warning("nenhum usuário: abra a interface para criar o administrador (primeira configuração)")
    if not settings.auth_enabled:
        log.warning("AUTH_ENABLED=false: qualquer pessoa com acesso à porta age como administrador")
    await orchestrator.recover()
    await asyncio.to_thread(brain.ensure_vault)
    watcher.start(asyncio.get_running_loop())
    tasks = [
        asyncio.create_task(health_loop()),
        asyncio.create_task(orchestrator.consume_detections()),
        asyncio.create_task(mcp_server.serve()),
        asyncio.create_task(orchestrator.escalation_loop()),
    ]
    log.info(
        "Hermes Sentinel no ar · gateway=%s · kubeconfig=%s", settings.hermes_gateway_url, settings.kubeconfig_path
    )
    yield
    watcher.stop()
    for t in tasks:
        t.cancel()


app = FastAPI(
    title="Hermes Sentinel API",
    version="0.1.0",
    description="AIOps para Kubernetes: detecção determinística, investigação pelo Hermes e remediação com aprovação humana.",
    lifespan=lifespan,
)
app.include_router(auth_api.router)
app.include_router(admin_api.router)
app.include_router(incidents_api.router)
app.include_router(governance_api.router)
app.include_router(workspace_api.router)
app.include_router(operations_api.router)
app.include_router(integrations_api.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,  # cookie de sessão HttpOnly
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


# --------------------------------------------------------------------------- REST
@app.middleware("http")
async def reject_cross_site_writes(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Defesa contra CSRF além do SameSite=Lax: escrita só de origens conhecidas."""
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin not in settings.cors_origins:
        return JSONResponse({"detail": "origem não permitida"}, status_code=403)
    return await call_next(request)


@app.get("/api/healthz", tags=["saúde"], summary="Liveness (público, sem detalhes)")
async def healthz() -> dict:
    return {"ok": True}


@app.get("/api/health", tags=["saúde"])
async def health(_: Annotated[Principal, Depends(require("health:read"))]) -> dict:
    data = await collect_health()
    await bus.publish_health(data)
    return data


@app.get("/api/state")
async def state(_: Annotated[Principal, Depends(require("incidents:read"))]) -> dict:
    snap = bus.snapshot()
    snap["pendingApprovals"] = orchestrator.pending_approvals
    return snap


@app.post("/api/simulate/incident", status_code=202, tags=["simulação"])
async def simulate_incident(
    actor: Annotated[Actor, Depends(actor_for("incidents:simulate"))], req: SimulateRequest | None = None
) -> dict:
    req = req or SimulateRequest()
    inc = orchestrator.simulate(req)
    await repo.audit(actor.name, "incident.simulate", inc.id, {"type": req.type, "useAi": req.useAi}, actor.ip)
    return {"incidentId": inc.id, "type": inc.type, "useAi": req.useAi, "simulated": True}


@app.post("/api/test-communication", status_code=202)
async def test_communication(_: Annotated[Principal, Depends(require("incidents:simulate"))]) -> dict:
    orchestrator._spawn(orchestrator.test_communication())  # guarda a referência da task
    return {"started": True}


# --------------------------------------------------------------------------- WebSocket
@app.websocket("/ws/telemetry")
async def telemetry(ws: WebSocket) -> None:
    origin = ws.headers.get("origin")
    if origin and origin not in settings.cors_origins:
        await ws.close(code=4403)
        return
    if await websocket_principal(ws) is None:
        await ws.close(code=4401)  # o frontend volta para a tela de login
        return
    await bus.connect(ws)
    try:
        for approval in orchestrator.pending_approvals:
            await ws.send_json({"type": "approval_pending", "timestamp": now_iso(), "approvalRequest": approval})
        while True:
            msg = await ws.receive_text()  # keepalive do cliente
            if msg == "ping":
                await ws.send_json({"type": "pong", "timestamp": now_iso()})
    except WebSocketDisconnect:
        pass
    finally:
        await bus.disconnect(ws)
