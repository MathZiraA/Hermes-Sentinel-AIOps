"""Fase 7: agente de cluster remoto: sinal → incidente → aprovação na central → comando → resultado verificado."""

from types import SimpleNamespace as NS

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from db import repository as repo
from schemas.events import ApprovalRequest

SIGNAL = {
    "type": "CrashLoopBackOff",
    "namespace": "loja",
    "pod": "carrinho-abc",
    "reason": "back-off",
    "kind": "Pod",
    "owner": "carrinho",
    "logs": "Connection refused",
    "events": "BackOff x9",
}


@pytest.fixture()
async def central(database, tmp_path, monkeypatch):
    from agents import orchestrator as mod
    from api import cluster_agents, deps
    from integrations import brain

    monkeypatch.setattr(deps, "settings", NS(auth_enabled=False))
    monkeypatch.setattr(mod, "STEP", 0)
    monkeypatch.setattr(brain, "root", lambda: tmp_path / "brain")
    o = mod.orchestrator
    o.incidents.clear()

    async def fake_run(inc, use_ai):  # investigação real exigiria IA; aqui vai direto ao pedido de aprovação
        await o._register(inc)
        await o._set_status(inc, "investigating")
        inc.approval = ApprovalRequest(
            incidentId=inc.id,
            action="rollout_restart",
            params={},
            command="kubectl rollout restart deployment/carrinho -n loja",
            description="",
            target="loja/carrinho",
        )
        await o._set_status(inc, "waiting_approval")

    monkeypatch.setattr(o, "run_incident", fake_run)
    await repo.ensure_cluster("local", "local")
    app = FastAPI()
    app.include_router(cluster_agents.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://central") as client:
        yield client, o


async def _drain(o):
    while o._tasks:
        for t in list(o._tasks):
            await t


async def test_fluxo_completo_do_agente(central):
    client, o = central
    reg = await client.post("/api/admin/clusters", json={"id": "loja-prod", "name": "Loja (produção)"})
    token = reg.json()["agentToken"]
    assert token.startswith("sca_")
    agent = {"Authorization": f"Bearer {token}"}

    assert (
        await client.post("/api/agent/v1/signals", json=[SIGNAL], headers={"Authorization": "Bearer x"})
    ).status_code == 401
    r = await client.post("/api/agent/v1/signals", json=[SIGNAL], headers=agent)
    inc_id = r.json()["incidents"][0]
    await _drain(o)
    inc = o.incidents[inc_id]
    assert inc.cluster == "loja-prod" and inc.source == "agent" and inc.deployment == "carrinho"
    again = await client.post("/api/agent/v1/signals", json=[{**SIGNAL, "pod": "carrinho-def"}], headers=agent)
    assert again.json()["incidents"] == [inc_id]  # mesmo workload: correlacionado

    await o.approve(inc_id, "", actor="ana@empresa.com")
    await _drain(o)
    assert inc.status == "remediating" and "enviado ao agente" in inc.remediationResult
    cmds = (await client.get("/api/agent/v1/commands", headers=agent)).json()
    assert [c["action"] for c in cmds] == ["rollout_restart"] and cmds[0]["workload"] == "carrinho"
    assert (await client.get("/api/agent/v1/commands", headers=agent)).json() == []  # entregue uma vez só

    done = await client.post(
        f"/api/agent/v1/commands/{cmds[0]['id']}/result",
        headers=agent,
        json={"ok": True, "result": "reiniciado", "healthy": True, "detail": "2/2 prontas"},
    )
    assert done.status_code == 200
    await _drain(o)
    assert inc.status == "postmortem"
    repeat = await client.post(
        f"/api/agent/v1/commands/{cmds[0]['id']}/result", headers=agent, json={"ok": True, "healthy": True}
    )
    assert repeat.status_code == 404


async def test_token_de_um_cluster_nao_serve_para_outro(central):
    client, _ = central
    t1 = (await client.post("/api/admin/clusters", json={"id": "a", "name": "A"})).json()["agentToken"]
    await client.post("/api/admin/clusters", json={"id": "b", "name": "B"})
    hb = await client.post(
        "/api/agent/v1/heartbeat", json={"version": "1.0.0"}, headers={"Authorization": f"Bearer {t1}"}
    )
    assert hb.json() == {"cluster": "a"}
    assert (await client.post("/api/admin/clusters", json={"id": "Inválido!", "name": "x"})).status_code == 422


async def test_metricas_prometheus_e_probes(database):
    import main

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://t") as client:
        body = (await client.get("/metrics")).text
        assert "sentinel_open_incidents" in body and "sentinel_websocket_clients" in body
        assert (await client.get("/api/readyz")).json() == {"ok": True}
