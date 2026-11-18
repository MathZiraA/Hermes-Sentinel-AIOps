"""Detecção abrangente do Monitor: qualquer coisa fora do normal, não só 3 nomes."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

from k8s import watcher as w

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
OLD = NOW - timedelta(minutes=10)
NEW = NOW - timedelta(seconds=20)


def _cs(name="app", ready=False, waiting=None, last=None, restarts=0):
    return NS(
        name=name,
        ready=ready,
        restart_count=restarts,
        state=NS(waiting=waiting, terminated=None),
        last_state=NS(terminated=last),
    )


def _pod(phase="Running", statuses=(), conditions=(), created=OLD, reason=None, message=None):
    return NS(
        metadata=NS(namespace="stockflow", name="p-1", creation_timestamp=created),
        spec=NS(containers=[NS(name="app", resources=NS(limits=None))]),
        status=NS(
            phase=phase,
            reason=reason,
            message=message,
            container_statuses=list(statuses),
            init_container_statuses=None,
            conditions=list(conditions),
        ),
    )


def _types(dets):
    return [d.type for d in dets]


def test_motivo_de_espera_desconhecido_vira_incidente_com_o_proprio_nome():
    p = _pod(statuses=[_cs(waiting=NS(reason="CreateContainerConfigError", message='configmap "x" not found'))])
    assert _types(w.classify_pod(p, NOW)) == ["CreateContainerConfigError"]


def test_estado_de_boot_nao_e_alarme():
    p = _pod(phase="Pending", statuses=[_cs(waiting=NS(reason="ContainerCreating", message=""))], created=NEW)
    assert w.classify_pod(p, NOW) == []


def test_pod_evicted():
    p = _pod(phase="Failed", reason="Evicted", message="The node was low on resource: memory.")
    assert _types(w.classify_pod(p, NOW)) == ["Evicted"]


def test_pending_sem_no_so_depois_da_carencia():
    cond = [
        NS(
            type="PodScheduled",
            status="False",
            reason="Unschedulable",
            message="0/1 nodes: Insufficient cpu",
            last_transition_time=OLD,
        )
    ]
    assert _types(w.classify_pod(_pod(phase="Pending", conditions=cond, created=OLD), NOW)) == ["FailedScheduling"]
    assert w.classify_pod(_pod(phase="Pending", conditions=cond, created=NEW), NOW) == []


def test_running_mas_nao_pronto_por_muito_tempo():
    cond = [NS(type="Ready", status="False", last_transition_time=OLD, reason=None, message=None)]
    p = _pod(statuses=[_cs(ready=False)], conditions=cond)
    [d] = w.classify_pod(p, NOW)
    assert d.type == "NotReady" and d.container == "app"


def test_no_com_pressao_de_disco_e_fora_do_ar():
    node = NS(
        metadata=NS(name="kind-control-plane"),
        status=NS(
            conditions=[
                NS(type="Ready", status="False", message="kubelet stopped", reason=None),
                NS(type="DiskPressure", status="True", message="disk 95%", reason=None),
                NS(type="MemoryPressure", status="False", message="", reason=None),
            ]
        ),
    )
    assert _types(w.classify_node(node)) == ["NodeNotReady", "NodeDiskPressure"]


def test_deployment_fora_do_ar():
    dep = NS(
        metadata=NS(namespace="stockflow", name="gateway"),
        spec=NS(replicas=2),
        status=NS(
            available_replicas=0,
            conditions=[NS(type="Available", status="False", last_transition_time=OLD, reason=None, message=None)],
        ),
    )
    [d] = w.classify_deployment(dep, NOW)
    assert d.type == "DeploymentDown" and d.kind == "Deployment"


def test_job_que_falhou_e_pvc_pendente():
    job = NS(
        metadata=NS(namespace="stockflow", name="backup"),
        status=NS(conditions=[NS(type="Failed", status="True", reason="BackoffLimitExceeded", message="x")]),
    )
    pvc = NS(
        metadata=NS(namespace="stockflow", name="dados", creation_timestamp=OLD),
        spec=NS(storage_class_name="inexistente"),
        status=NS(phase="Pending"),
    )
    assert _types(w.classify_job(job)) == ["JobFailed"]
    assert _types(w.classify_pvc(pvc, NOW)) == ["PVCPending"]


def test_evento_warning_generico_repetido():
    ev = NS(
        type="Warning",
        reason="FailedMount",
        count=5,
        message='secret "db" not found',
        metadata=NS(namespace="stockflow"),
        involved_object=NS(kind="Pod", name="p-1"),
    )
    assert _types(w.classify_event(ev)) == ["FailedMount"]
    ev.count = 1
    assert w.classify_event(ev) == []
    ev.count, ev.reason = 9, "BackOff"  # já coberto pela regra de pod
    assert w.classify_event(ev) == []


def test_memoria_perto_do_limite_avisa_antes_do_oom():
    assert _types(w.classify_memory("stockflow", "p-1", "app", "60Mi", "64Mi")) == ["MemoryNearLimit"]
    assert w.classify_memory("stockflow", "p-1", "app", "30Mi", "64Mi") == []
    assert w.parse_bytes("1Gi") == 2**30


def test_pod_sendo_apagado_nao_e_falha_e_dono_vem_do_proprio_pod():
    p = _pod(phase="Failed", reason=None, message=None)
    p.metadata.owner_references = [NS(kind="ReplicaSet", name="estoque-sync-9bdf9ff69")]
    p.metadata.deletion_timestamp = None
    [d] = w.classify_pod(p, NOW)
    assert d.owner == "estoque-sync"
    p.metadata.deletion_timestamp = NOW
    assert w.classify_pod(p, NOW) == []
