"""Fase 4: catálogo de ações, silêncios, autorremediação, verificação pós-correção e escalonamento."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from db import operations as ops
from db import repository as repo
from domain import actions as catalog
from identity import service
from schemas.events import Incident

NOW = datetime.now(UTC)


# --------------------------------------------------------------------------- catálogo (puro)
def test_catalogo_valida_parametros_e_gera_o_comando():
    assert catalog.validate("scale", {"replicas": 3}) == {"replicas": 3}
    with pytest.raises(catalog.InvalidAction):
        catalog.validate("scale", {"replicas": 9})
    p = catalog.validate("set_resources", {"container": "relatorios", "memory_limit": "256Mi"})
    cmd = catalog.command("set_resources", namespace="stockflow", workload="relatorios", pod="x", kind="Pod", params=p)
    assert cmd == "kubectl set resources deployment/relatorios -c relatorios --limits=memory=256Mi -n stockflow"
    for bad in ({"container": "x", "memory_limit": "999Gi"}, {"container": "x"}, {"memory_limit": "256Mi"}):
        with pytest.raises(catalog.InvalidAction):
            catalog.validate("set_resources", bad)
    with pytest.raises(catalog.InvalidAction):
        catalog.validate("rm -rf", {})
    assert {a.id for a in catalog.ACTIONS.values() if a.auto_eligible} == {"rollout_restart", "delete_pod", "rerun_job"}


# --------------------------------------------------------------------------- silêncios e políticas
async def test_silencio_cobre_so_o_que_casa_e_expira(database):
    s = await ops.create_silence(
        cluster="*",
        namespace="stockflow",
        workload="pagamentos*",
        incident_type="*",
        starts_at=NOW - timedelta(minutes=1),
        ends_at=NOW + timedelta(hours=1),
        reason="deploy planejado",
        created_by="ana",
    )
    assert await ops.active_silence("local", "stockflow", "pagamentos-v2", "ImagePullBackOff")
    assert await ops.active_silence("local", "stockflow", "pedidos", "OOMKilled") is None
    await ops.expire_silence(s["id"])
    assert await ops.active_silence("local", "stockflow", "pagamentos-v2", "ImagePullBackOff") is None
    with pytest.raises(ValueError):
        await ops.create_silence(
            cluster="*",
            namespace="*",
            workload="*",
            incident_type="*",
            starts_at=NOW,
            ends_at=NOW - timedelta(minutes=1),
            reason="x",
            created_by="ana",
        )


async def test_politica_so_aceita_baixo_risco_e_respeita_limite(database):
    with pytest.raises(catalog.InvalidAction):
        await ops.create_policy(
            cluster="*",
            namespace="*",
            workload="*",
            incident_type="NodeNotReady",
            action="drain",
            max_per_hour=1,
            created_by="admin",
        )
    await ops.create_policy(
        cluster="*",
        namespace="stockflow",
        workload="relatorios",
        incident_type="OOMKilled",
        action="rollout_restart",
        max_per_hour=1,
        created_by="admin",
    )
    assert await ops.matching_policy("local", "stockflow", "relatorios", "OOMKilled", "rollout_restart")
    assert await ops.matching_policy("local", "stockflow", "relatorios", "OOMKilled", "rollout_restart") is None
    assert await ops.matching_policy("local", "stockflow", "pedidos", "OOMKilled", "rollout_restart") is None


# --------------------------------------------------------------------------- fluxo no orquestrador
@pytest.fixture()
async def orch(database, tmp_path, monkeypatch):
    from agents import orchestrator as mod
    from config import settings
    from integrations import brain

    fast = dataclasses.replace(settings, verify_delay_seconds=0, verify_interval_seconds=0, verify_attempts=2)
    monkeypatch.setattr(mod, "settings", fast)
    monkeypatch.setattr(mod, "STEP", 0)
    monkeypatch.setattr(brain, "root", lambda: tmp_path / "brain")
    ops._auto_runs.clear()
    mod.orchestrator.incidents.clear()
    await repo.ensure_cluster("local", "local")
    return mod


async def _drain(o):
    while o._tasks:
        for t in list(o._tasks):
            await t


async def _investigated(o, **kw) -> Incident:
    base = dict(
        id="INC-A",
        type="OOMKilled",
        namespace="stockflow",
        pod="relatorios-x",
        deployment="relatorios",
        reason="exit 137",
        cluster="local",
    )
    base.update(kw)
    inc = Incident(**base)
    await o._register(inc)
    await o._set_status(inc, "investigating")
    return inc


async def test_autorremediacao_aplica_verifica_e_resolve(orch, monkeypatch):
    o = orch.orchestrator
    applied = []

    async def fake_apply(inc):
        applied.append(inc.approval.command)
        return "deployment/relatorios reiniciado"

    monkeypatch.setattr(o, "_apply", fake_apply)
    monkeypatch.setattr(orch.k8s, "workload_healthy", lambda kind, ns, name: (True, "1/1 prontas"))
    await ops.create_policy(
        cluster="*",
        namespace="stockflow",
        workload="relatorios",
        incident_type="OOMKilled",
        action="rollout_restart",
        max_per_hour=2,
        created_by="admin",
    )
    inc = await _investigated(o)
    await o._request_approval(inc, {"recommendedAction": {"type": "rollout_restart"}, "rootCause": "OOM"})
    await _drain(o)
    assert applied == ["kubectl rollout restart deployment/relatorios -n stockflow"]
    assert inc.status == "postmortem" and inc.decisionBy.startswith("politica:") and inc.autoRemediatedBy
    _, timeline = await repo.get_incident("INC-A")
    assert any(e["kind"] == "verify" and "1/1" in e["text"] for e in timeline)
    actions = [e["action"] for e in (await repo.list_audit())[0]]
    assert "remediation.auto_approve" in actions


async def test_sem_politica_espera_aprovacao_e_acao_invalida_vira_manual(orch):
    o = orch.orchestrator
    inc = await _investigated(o, id="INC-B")
    await o._request_approval(inc, {"recommendedAction": {"type": "scale", "replicas": 50}, "rootCause": "x"})
    assert inc.status == "waiting_approval" and inc.approval.action == "none"
    assert "inválida" in inc.approval.description


async def test_verificacao_reabre_uma_vez_e_depois_falha(orch, monkeypatch):
    o = orch.orchestrator
    reruns = []

    async def fake_run(inc, use_ai):
        reruns.append(inc.id)

    monkeypatch.setattr(o, "run_incident", fake_run)
    monkeypatch.setattr(orch.k8s, "workload_healthy", lambda kind, ns, name: (False, "0/1 prontas"))
    inc = await _investigated(o, id="INC-C")
    await o._request_approval(inc, {"recommendedAction": {"type": "rollout_restart"}, "rootCause": "x"})
    inc.approval.params = {}
    await o._set_status(inc, "remediating")
    await o._set_status(inc, "monitoring")
    await o._verify(inc)
    await _drain(o)
    assert inc.status == "investigating" and inc.reopenCount == 1 and reruns == ["INC-C"]
    await o._set_status(inc, "waiting_approval")
    await o._set_status(inc, "remediating")
    await o._set_status(inc, "monitoring")
    await o._verify(inc)
    await _drain(o)
    assert inc.status == "failed"


async def test_escalonamento_vai_do_plantao_aos_admins(orch):
    o = orch.orchestrator
    await service.create_user("admin@empresa.com", "Admin", "admin", "Admin-Senha-Forte-1")
    await service.create_user("op@empresa.com", "Op", "operator", "Oper-Senha-Forte-1")
    team = await service.create_team("SRE")
    await service.set_team(team["id"], ["op@empresa.com"], [{"cluster": "*", "namespace": "stockflow"}])
    await ops.add_shift(team["id"], "op@empresa.com", 1, NOW - timedelta(hours=1), NOW + timedelta(hours=8))
    inc = await _investigated(o, id="INC-D")
    await o.escalate(inc, 1)
    assert inc.assignedTo == ["op@empresa.com"] and inc.escalationLevel == 1
    await o.escalate(inc, 2)  # sem secundário: continua com o primário
    assert inc.assignedTo == ["op@empresa.com"] and inc.escalationLevel == 2
    await o.escalate(inc, 3)
    assert inc.assignedTo == ["admin@empresa.com"] and inc.escalationLevel == 3
    other = await _investigated(o, id="INC-E", namespace="financeiro")
    await o.escalate(other, 1)  # ninguém responde por esse namespace: vai direto aos admins
    assert other.assignedTo == ["admin@empresa.com"] and other.escalationLevel == 3
