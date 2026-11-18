"""Hermes Sentinel — backend local (sensor/executor do k8s + orquestração com o Hermes no VPS).

cd backend && .venv/bin/uvicorn main:app --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import mcp_server
from agents.orchestrator import orchestrator
from config import settings
from core.bus import bus
from integrations import obsidian
from integrations.github_itsm import github_configured
from integrations.hermes_client import hermes
from k8s.client import k8s
from k8s.watcher import watcher
from schemas.events import DecisionRequest, SimulateRequest, now_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sentinel")

HEALTH_INTERVAL = 30  # s — health checks não usam IA (GET /v1/models)


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
        "mcp": {
            "ok": bool(settings.mcp_token),
            "port": settings.mcp_port,
            "detail": f"127.0.0.1:{settings.mcp_port}/mcp" if settings.mcp_token else "SENTINEL_MCP_TOKEN não definido",
        },
        "websocketClients": bus.client_count,
    }


async def health_loop() -> None:
    while True:
        with suppress(Exception):
            await bus.publish_health(await collect_health())
        await asyncio.sleep(HEALTH_INTERVAL)


@asynccontextmanager
async def lifespan(_: FastAPI):
    from integrations import brain

    await asyncio.to_thread(brain.ensure_vault)
    watcher.start(asyncio.get_running_loop())
    tasks = [
        asyncio.create_task(health_loop()),
        asyncio.create_task(orchestrator.consume_detections()),
        asyncio.create_task(mcp_server.serve()),
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# --------------------------------------------------------------------------- REST
@app.get("/api/health")
async def health() -> dict:
    data = await collect_health()
    await bus.publish_health(data)
    return data


@app.get("/api/state")
async def state() -> dict:
    snap = bus.snapshot()
    snap["pendingApprovals"] = orchestrator.pending_approvals
    return snap


@app.get("/api/incidents")
async def incidents() -> list[dict]:
    return [i.model_dump(exclude={"logs", "events"}) for i in orchestrator.incidents.values()]


@app.post("/api/simulate/incident", status_code=202)
async def simulate_incident(req: SimulateRequest | None = None) -> dict:
    inc = orchestrator.simulate(req or SimulateRequest())
    return {"incidentId": inc.id, "type": inc.type, "useAi": (req or SimulateRequest()).useAi, "simulated": True}


@app.post("/api/agents/approve/{incident_id}")
async def approve(incident_id: str, body: DecisionRequest | None = None) -> dict:
    try:
        inc = await orchestrator.approve(incident_id, (body or DecisionRequest()).motivo)
    except KeyError as exc:
        raise HTTPException(404, "incidente inexistente ou sem aprovação pendente") from exc
    return {"incidentId": inc.id, "status": inc.status, "command": inc.approval.command if inc.approval else None}


@app.post("/api/agents/reject/{incident_id}")
async def reject(incident_id: str, body: DecisionRequest | None = None) -> dict:
    try:
        inc = await orchestrator.reject(incident_id, (body or DecisionRequest()).motivo)
    except KeyError as exc:
        raise HTTPException(404, "incidente inexistente ou sem aprovação pendente") from exc
    return {"incidentId": inc.id, "status": inc.status}


@app.post("/api/test-communication", status_code=202)
async def test_communication() -> dict:
    orchestrator._spawn(orchestrator.test_communication())  # guarda a referência da task
    return {"started": True}


# --------------------------------------------------------------------------- WebSocket
@app.websocket("/ws/telemetry")
async def telemetry(ws: WebSocket) -> None:
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
