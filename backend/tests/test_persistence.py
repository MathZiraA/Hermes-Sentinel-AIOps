"""Fase 1: ciclo de vida, SEV/SLA, persistência, auditoria imutável e API de incidentes."""

import itertools
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from db import engine as db
from db import repository as repo
from domain.lifecycle import InvalidTransition, SlaPolicy, check_transition, severity_for
from schemas.events import ApprovalRequest, Incident

T0 = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- domínio (puro)
def test_ciclo_de_vida_permite_o_caminho_feliz_e_barra_atalhos():
    path = ["detected", "acknowledged", "investigating", "waiting_approval", "remediating", "monitoring", "resolved"]
    for a, b in itertools.pairwise(path):
        check_transition(a, b)
    check_transition("resolved", "postmortem")
    check_transition("monitoring", "investigating")  # reabrir se a correção não resolveu
    for a, b in [("detected", "remediating"), ("waiting_approval", "resolved"), ("postmortem", "investigating")]:
        with pytest.raises(InvalidTransition):
            check_transition(a, b)


def test_severidade_por_tipo_e_fallback():
    assert severity_for("NodeNotReady") == "SEV1"
    assert severity_for("OOMKilled") == "SEV2"
    assert severity_for("JobFailed") == "SEV3"
    assert severity_for("MemoryNearLimit") == "SEV4"
    assert severity_for("AlgoNovo", "crítica") == "SEV1"
    assert severity_for("AlgoNovo") == "SEV3"


def test_sla_estoura_quando_passa_do_prazo():
    sla = SlaPolicy("5,15,60,1440", "60,240,1440,4320")
    ok = sla.evaluate("SEV1", T0, T0 + timedelta(minutes=3), None, T0 + timedelta(minutes=30))
    late = sla.evaluate("SEV1", T0, None, None, T0 + timedelta(minutes=90))
    assert ok["ackBreached"] is False and ok["resolveBreached"] is False
    assert late["ackBreached"] is True and late["resolveBreached"] is True
    assert SlaPolicy("lixo", "").ack == (5, 15, 60, 1440)  # configuração inválida cai no padrão


# --------------------------------------------------------------------------- persistência
def _inc(**kw) -> Incident:
    base = dict(
        id="INC-1",
        type="OOMKilled",
        namespace="stockflow",
        pod="relatorios-x",
        deployment="relatorios",
        reason="exit 137",
        sev="SEV2",
    )
    base.update(kw)
    return Incident(**base)


async def test_incidente_e_linha_do_tempo_sobrevivem(database):
    await repo.ensure_cluster("local", "kind-stockflow")
    inc = _inc()
    await repo.save_incident(inc)
    await repo.add_event(inc.id, "Monitor detectou OOMKilled")
    inc.status = "investigating"
    await repo.save_incident(inc)
    loaded, timeline = await repo.get_incident("INC-1")
    assert loaded.status == "investigating" and timeline[0]["text"] == "Monitor detectou OOMKilled"
    items, total = await repo.list_incidents(status=["investigating"], query="relat")
    assert total == 1 and items[0].id == "INC-1"
    assert (await repo.open_incidents())[0].id == "INC-1"
    assert (await repo.list_clusters())[0]["openIncidents"] == 1


async def test_auditoria_encadeada_detecta_e_impede_adulteracao(database):
    await repo.audit("ana", "remediation.approve", "INC-1", {"command": "kubectl rollout restart x"}, "10.0.0.1")
    await repo.audit("bia", "remediation.reject", "INC-2", {"motivo": "config"}, None)
    ok = await repo.verify_audit()
    assert ok["ok"] is True and ok["entries"] == 2
    async with db.session() as s:
        with pytest.raises(Exception, match="imutável"):
            await s.execute(text("UPDATE audit_log SET actor = 'mallory'"))
    async with db.session() as s:
        with pytest.raises(Exception, match="imutável"):
            await s.execute(text("DELETE FROM audit_log"))
    csv_out = await repo.export_audit("csv")
    assert csv_out.splitlines()[0].startswith("id,ts,actor") and "ana" in csv_out


async def test_resumo_calcula_mtta_e_mttr(database):
    await repo.ensure_cluster("local", "local")
    now = datetime.now(UTC)
    inc = _inc(
        detectedAt=(now - timedelta(minutes=30)).isoformat(),
        acknowledgedAt=(now - timedelta(minutes=20)).isoformat(),
        resolvedAt=now.isoformat(),
        status="resolved",
        decision="approved",
    )
    await repo.save_incident(inc)
    s = await repo.summary(days=7)
    assert s["incidents"] == 1 and s["mttaMinutes"] == 10.0 and s["mttrMinutes"] == 30.0
    assert s["bySev"] == {"SEV2": 1} and s["decisions"]["approved"] == 1


# --------------------------------------------------------------------------- API
@pytest.fixture()
async def api(database, tmp_path, monkeypatch):
    from agents import orchestrator as orch_mod
    from api import deps, governance, incidents
    from integrations import brain

    monkeypatch.setattr(deps, "settings", NS(auth_enabled=False))  # Fase 1 testa o fluxo, não o login
    monkeypatch.setattr(orch_mod, "STEP", 0)
    monkeypatch.setattr(brain, "root", lambda: tmp_path / "brain")
    orch_mod.orchestrator.incidents.clear()
    app = FastAPI()
    app.include_router(incidents.router)
    app.include_router(governance.router)
    await repo.ensure_cluster("local", "local")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, orch_mod.orchestrator


async def _waiting(orch, **kw) -> Incident:
    inc = _inc(simulated=True, **kw)
    await orch._register(inc)
    await orch._set_status(inc, "investigating")
    inc.approval = ApprovalRequest(
        incidentId=inc.id,
        action="none",
        command="(nenhuma)",
        description="",
        target="stockflow/relatorios",
        simulated=True,
    )
    await orch._set_status(inc, "waiting_approval")
    return inc


async def test_api_reconhecer_aprovar_e_auditar(api):
    client, orch = api
    await _waiting(orch)
    r = await client.post("/api/incidents/INC-1/acknowledge")
    assert r.status_code == 200 and r.json()["acknowledgedBy"] == "operador"
    r = await client.post("/api/agents/approve/INC-1", json={"motivo": "pode seguir"})
    assert r.status_code == 200 and r.json()["status"] in ("remediating", "resolved", "postmortem")
    for task in list(orch._tasks):
        await task
    detail = (await client.get("/api/incidents/INC-1")).json()
    assert detail["status"] == "postmortem" and detail["decisionBy"] == "operador"
    assert any(e["kind"] == "decision" for e in detail["timeline"])
    assert "sla" in detail and detail["statusLabel"] == "Post-mortem"
    audit = (await client.get("/api/audit")).json()
    assert [e["action"] for e in audit["items"]] == ["remediation.approve", "incident.acknowledge"]
    assert (await client.get("/api/audit/verify")).json()["ok"] is True


async def test_api_rejeitar_fecha_sem_alterar_e_separa_deveres(api):
    client, orch = api
    await _waiting(orch, id="INC-2")
    assert (await client.post("/api/agents/reject/INC-2", json={"motivo": "  "})).status_code == 422
    r = await client.post("/api/agents/reject/INC-2", json={"motivo": "config errada"})
    assert r.json()["status"] == "closed"
    inc3 = await _waiting(orch, id="INC-3")
    inc3.proposedBy = "operador"  # a mesma pessoa que vai decidir
    r = await client.post("/api/agents/approve/INC-3")
    assert r.status_code == 403
    assert (await client.post("/api/agents/approve/NAO-EXISTE")).status_code == 404


async def test_incidentes_abertos_sao_retomados_apos_reinicio(api):
    _, orch = api
    await _waiting(orch, id="INC-9")
    orch.incidents.clear()  # simula o processo reiniciando
    assert await orch.recover() == 1
    assert orch.incidents["INC-9"].status == "waiting_approval"
    assert orch.pending_approvals[0]["incidentId"] == "INC-9"
