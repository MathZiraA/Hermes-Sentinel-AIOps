"""Fase 5: Jira, Zabbix, Grafana e Loki, com as APIs externas simuladas (nada sai para a internet)."""

import dataclasses
import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from config import settings
from db import repository as repo
from integrations import jira, observability
from schemas.events import Incident


def _inc(**kw) -> Incident:
    base = dict(
        id="INC-J",
        type="OOMKilled",
        namespace="stockflow",
        pod="relatorios-x",
        deployment="relatorios",
        reason="exit 137",
        sev="SEV2",
        detectedAt="2026-11-18T12:00:00+00:00",
        assignedTo=["op@empresa.com"],
    )
    base.update(kw)
    return Incident(**base)


# --------------------------------------------------------------------------- Jira
@pytest.fixture()
def jira_api(monkeypatch):
    cfg = dataclasses.replace(
        settings,
        jira_url="https://empresa.atlassian.net",
        jira_email="bot@empresa.com",
        jira_api_token="tok",
        jira_project="OPS",
        jira_done_transition="Done",
    )
    monkeypatch.setattr(jira, "settings", cfg)
    jira._account_ids.clear()
    calls: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        calls.append((request.method, request.url.path, body))
        path = request.url.path
        if path == "/rest/api/3/issue" and request.method == "POST":
            return httpx.Response(201, json={"key": "OPS-7"})
        if path == "/rest/api/3/user/search":
            return httpx.Response(200, json=[{"accountId": "acc-op"}])
        if path.endswith("/transitions") and request.method == "GET":
            return httpx.Response(200, json={"transitions": [{"id": "31", "name": "Done", "to": {"name": "Done"}}]})
        return httpx.Response(204)

    monkeypatch.setattr(jira, "_transport", httpx.MockTransport(handler))
    return calls


async def test_jira_abre_atribui_comenta_e_fecha(jira_api):
    inc = _inc()
    await jira.channel("opened", inc, "plantão primário: op@empresa.com")
    assert inc.ticket == {"system": "jira", "key": "OPS-7", "url": "https://empresa.atlassian.net/browse/OPS-7"}
    created = next(b for m, p, b in jira_api if p == "/rest/api/3/issue")
    assert created["fields"]["project"] == {"key": "OPS"} and created["fields"]["priority"] == {"name": "High"}
    assert ("PUT", "/rest/api/3/issue/OPS-7/assignee", {"accountId": "acc-op"}) in jira_api
    comment = next(b for m, p, b in jira_api if p.endswith("/comment"))
    assert comment["body"]["content"][-1]["content"][0] == {"type": "mention", "attrs": {"id": "acc-op"}}
    jira_api.clear()
    await jira.channel("resolved", inc, "Resolvido e verificado")
    assert ("POST", "/rest/api/3/issue/OPS-7/transitions", {"transition": {"id": "31"}}) in jira_api
    assert not any(p == "/rest/api/3/issue" for _, p, _ in jira_api)  # não cria outro ticket


async def test_jira_ignora_simulados_por_padrao(jira_api):
    await jira.channel("opened", _inc(simulated=True), "x")
    assert jira_api == []


# --------------------------------------------------------------------------- Grafana e Loki
def test_link_do_grafana_cobre_o_intervalo_do_incidente(monkeypatch):
    monkeypatch.setattr(
        observability,
        "settings",
        dataclasses.replace(settings, grafana_url="https://grafana.empresa", grafana_dashboard_uid="k8s"),
    )
    link = observability.grafana_link(_inc())
    assert link.startswith("https://grafana.empresa/d/k8s?")
    start_ms = int(datetime(2026, 11, 18, 11, 30, tzinfo=UTC).timestamp() * 1000)  # 30 min antes da detecção
    assert "var-workload=relatorios" in link and f"from={start_ms}" in link


async def test_loki_monta_a_consulta_e_ordena_as_linhas(monkeypatch):
    monkeypatch.setattr(observability, "settings", dataclasses.replace(settings, loki_url="http://loki:3100"))
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["query"] = request.url.params["query"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "result": [
                        {"values": [["2", "segunda"], ["1", "primeira"]]},
                    ]
                }
            },
        )

    monkeypatch.setattr(observability, "_transport", httpx.MockTransport(handler))
    out = await observability.loki_logs("stockflow", "relatorios", contains="ERROR")
    assert seen["query"] == '{namespace="stockflow", app="relatorios"} |= "ERROR"'
    assert out == "primeira\nsegunda"


# --------------------------------------------------------------------------- Zabbix
@pytest.fixture()
async def zabbix(database, monkeypatch, tmp_path):
    from agents import orchestrator as mod
    from api import integrations as api_mod
    from integrations import brain

    monkeypatch.setattr(api_mod, "settings", dataclasses.replace(settings, zabbix_webhook_token="segredo-zbx"))
    monkeypatch.setattr(mod, "STEP", 0)
    monkeypatch.setattr(brain, "root", lambda: tmp_path / "brain")
    started = []

    async def fake_run(inc, use_ai):
        await mod.orchestrator._register(inc)
        started.append(inc)

    monkeypatch.setattr(mod.orchestrator, "run_incident", fake_run)
    mod.orchestrator.incidents.clear()
    await repo.ensure_cluster("local", "local")
    app = FastAPI()
    app.include_router(api_mod.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        yield client, started, mod.orchestrator


EVENT = {
    "event_id": "991",
    "status": "PROBLEM",
    "host": "db-01",
    "trigger": "Disco acima de 90%",
    "severity": "High",
    "message": "/var 93%",
    "namespace": "stockflow",
    "event_url": "https://zbx/tr?e=991",
}


async def test_zabbix_exige_token_e_vira_incidente_uma_vez(zabbix):
    client, started, orch = zabbix
    assert (await client.post("/api/integrations/zabbix", json=EVENT)).status_code == 401
    auth = {"Authorization": "Bearer segredo-zbx"}
    r = await client.post("/api/integrations/zabbix", json=EVENT, headers=auth)
    assert r.status_code == 202
    for t in list(orch._tasks):
        await t
    inc = started[0]
    assert inc.type == "ZabbixAlert" and inc.sev == "SEV2" and inc.source == "zabbix"
    assert inc.external["event_url"] == "https://zbx/tr?e=991"
    again = await client.post("/api/integrations/zabbix", json=EVENT, headers=auth)
    assert again.json()["incidentId"] == inc.id and len(started) == 1  # mesmo evento: mesmo incidente
    await client.post("/api/integrations/zabbix", json={**EVENT, "status": "RESOLVED"}, headers=auth)
    assert any("resolvido" in r for r in inc.related)
