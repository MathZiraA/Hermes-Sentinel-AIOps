"""Agente Monitor: detecção determinística e ABRANGENTE (0 chamadas de IA enquanto o cluster está saudável).

Duas fontes, numa thread (a lib `kubernetes` é síncrona):
- watch de Pods: reage em segundos a falhas de container;
- varredura periódica (SWEEP_SECONDS): nós, deployments, statefulsets, jobs, PVCs, HPAs,
  eventos Warning e uso de memória, além das regras que dependem de tempo (Pending há X min).

A regra é "qualquer coisa fora do normal", não uma lista fechada de nomes: um motivo de espera
desconhecido vira um incidente com o próprio nome, e o Investigator investiga do zero.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from config import settings
from k8s.client import K8sUnavailable, k8s

log = logging.getLogger("sentinel.watcher")

# Nomes canônicos para motivos equivalentes; o resto passa com o próprio nome
WAITING_ALIASES = {"ErrImagePull": "ImagePullBackOff"}
# Estados de espera normais durante o boot
BENIGN_WAITING = {"ContainerCreating", "PodInitializing"}
# Eventos Warning já cobertos por regras mais precisas (evita incidente duplicado)
COVERED_EVENT_REASONS = {"BackOff", "Failed", "FailedScheduling", "Unhealthy", "Evicted", "Killing"}
IGNORED_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease", "local-path-storage"}
COOLDOWN_SECONDS = 600
SWEEP_SECONDS = 30
PENDING_GRACE = 120  # Pod sem nó há mais que isso → FailedScheduling
NOT_READY_GRACE = 180  # Running mas não pronto (probe falhando) há mais que isso → NotReady
WORKLOAD_GRACE = 180  # Deployment/StatefulSet sem réplicas prontas há mais que isso
PVC_GRACE = 120
EVENT_MIN_COUNT = 3  # Warning genérico só vira incidente se repetiu
MEMORY_NEAR_LIMIT = 0.9  # uso ≥ 90% do limite → aviso antes do OOM


@dataclass(frozen=True)
class Detection:
    type: str
    namespace: str
    pod: str  # nome do objeto (pod, nó, deployment…)
    container: str
    reason: str
    kind: str = "Pod"
    severity: str = "alta"
    owner: str = ""  # workload dono (deployment/statefulset/job), quando dá para saber pelo próprio objeto


def _age(ts: Any, now: datetime | None = None) -> float:
    if not ts:
        return 0.0
    now = now or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return (now - ts).total_seconds()


def _cond(obj: Any, ctype: str) -> Any:
    for c in getattr(obj.status, "conditions", None) or []:
        if c.type == ctype:
            return c
    return None


# --------------------------------------------------------------------------- Pods
def _memory_limits(pod: Any) -> dict[str, str]:
    """container → limite de memória declarado (ex.: {"relatorios": "64Mi"})."""
    out: dict[str, str] = {}
    for c in getattr(getattr(pod, "spec", None), "containers", None) or []:
        limits = getattr(getattr(c, "resources", None), "limits", None) or {}
        if limits.get("memory"):
            out[c.name] = str(limits["memory"])
    return out


def _oom_reason(term: Any, mem_limit: str | None) -> str | None:
    """OOM explícito (reason=OOMKilled) ou provável: exit 137 (SIGKILL) num container com limite de memória.

    O kubelet só escreve OOMKilled quando o kernel mata o PID 1. Se morre um processo
    filho (worker do gunicorn/node, fork da JVM, `stress --vm`), o status vem como
    reason=Error + exit 137, e o pod acabaria rotulado como CrashLoopBackOff.
    """
    if not term:
        return None
    if term.reason == "OOMKilled":
        return f"exit {getattr(term, 'exit_code', 137)}"
    if getattr(term, "exit_code", None) == 137 and mem_limit:
        return f"exit 137 (SIGKILL) com limite de {mem_limit}: OOM provável"
    return None


def pod_owner(pod: Any) -> str:
    """Workload dono do pod sem chamar a API: ReplicaSet `app-7d9f8c6b5` → deployment `app`."""
    for ref in getattr(pod.metadata, "owner_references", None) or []:
        if ref.kind == "ReplicaSet":
            return ref.name.rsplit("-", 1)[0] if "-" in ref.name else ref.name
        if ref.kind in ("StatefulSet", "DaemonSet", "Job", "Deployment"):
            return ref.name
    return ""


def classify_pod(pod: Any, now: datetime | None = None) -> list[Detection]:
    """Regra pura (testável): devolve as anomalias visíveis no status do Pod."""
    if getattr(pod.metadata, "deletion_timestamp", None):
        return []  # pod sendo apagado (rollout, scale, delete manual): não é falha
    owner = pod_owner(pod)
    found = [_with_owner(d, owner) for d in _classify_pod(pod, now)]
    return found


def _with_owner(d: Detection, owner: str) -> Detection:
    return Detection(d.type, d.namespace, d.pod, d.container, d.reason, d.kind, d.severity, owner)


def _classify_pod(pod: Any, now: datetime | None = None) -> list[Detection]:
    found: list[Detection] = []
    ns = pod.metadata.namespace
    name = pod.metadata.name
    status = pod.status
    phase = getattr(status, "phase", None)

    # Pod inteiro falhou (Evicted, DeadlineExceeded, NodeLost…)
    if phase == "Failed":
        reason = getattr(status, "reason", None) or "PodFailed"
        return [Detection(reason, ns, name, "", (getattr(status, "message", None) or reason)[:200])]

    limits = _memory_limits(pod)
    all_statuses = list(getattr(status, "init_container_statuses", None) or []) + list(status.container_statuses or [])
    for cs in all_statuses:
        last_term = getattr(cs.last_state, "terminated", None)
        term = getattr(cs.state, "terminated", None)
        waiting = getattr(cs.state, "waiting", None)
        oom = _oom_reason(term, limits.get(cs.name)) or _oom_reason(last_term, limits.get(cs.name))
        if oom:
            found.append(Detection("OOMKilled", ns, name, cs.name, f"{oom} · restarts={cs.restart_count}"))
            continue
        if waiting and waiting.reason and waiting.reason not in BENIGN_WAITING:
            kind = WAITING_ALIASES.get(waiting.reason, waiting.reason)
            found.append(Detection(kind, ns, name, cs.name, (waiting.message or waiting.reason)[:200]))
    if found:
        return found

    # Regras que dependem de tempo
    if phase == "Pending":
        sched = _cond(pod, "PodScheduled")
        if sched is not None and sched.status == "False" and _age(pod.metadata.creation_timestamp, now) > PENDING_GRACE:
            found.append(Detection("FailedScheduling", ns, name, "", (sched.message or sched.reason or "sem nó")[:200]))
    elif phase == "Running" and status.container_statuses:
        ready = _cond(pod, "Ready")
        if ready is not None and ready.status == "False" and _age(ready.last_transition_time, now) > NOT_READY_GRACE:
            not_ready = [cs.name for cs in status.container_statuses if not cs.ready]
            found.append(
                Detection(
                    "NotReady",
                    ns,
                    name,
                    not_ready[0] if not_ready else "",
                    f"rodando mas não pronto há {int(_age(ready.last_transition_time, now) // 60)} min "
                    f"(probe falhando?) · containers: {', '.join(not_ready)}",
                )
            )
    return found


# --------------------------------------------------------------------------- outros recursos
def classify_node(node: Any) -> list[Detection]:
    name = node.metadata.name
    found: list[Detection] = []
    for c in getattr(node.status, "conditions", None) or []:
        if c.type == "Ready" and c.status != "True":
            found.append(
                Detection(
                    "NodeNotReady", "", name, "", (c.message or c.reason or "")[:200], kind="Node", severity="crítica"
                )
            )
        elif c.type in ("MemoryPressure", "DiskPressure", "PIDPressure") and c.status == "True":
            found.append(Detection(f"Node{c.type}", "", name, "", (c.message or c.reason or "")[:200], kind="Node"))
    return found


def classify_deployment(dep: Any, now: datetime | None = None) -> list[Detection]:
    ns, name, st = dep.metadata.namespace, dep.metadata.name, dep.status
    desired = dep.spec.replicas if dep.spec.replicas is not None else 1
    progressing = _cond(dep, "Progressing")
    if progressing is not None and progressing.reason == "ProgressDeadlineExceeded":
        return [
            Detection("ProgressDeadlineExceeded", ns, name, "", (progressing.message or "")[:200], kind="Deployment")
        ]
    available = _cond(dep, "Available")
    if (
        desired > 0
        and not (st.available_replicas or 0)
        and available is not None
        and available.status == "False"
        and _age(available.last_transition_time, now) > WORKLOAD_GRACE
    ):
        return [
            Detection(
                "DeploymentDown",
                ns,
                name,
                "",
                f"0/{desired} réplicas disponíveis",
                kind="Deployment",
                severity="crítica",
            )
        ]
    return []


def classify_statefulset(sts: Any, now: datetime | None = None) -> list[Detection]:
    desired = sts.spec.replicas if sts.spec.replicas is not None else 1
    ready = sts.status.ready_replicas or 0
    if desired > 0 and ready < desired and _age(sts.metadata.creation_timestamp, now) > WORKLOAD_GRACE:
        return [
            Detection(
                "StatefulSetDegraded",
                sts.metadata.namespace,
                sts.metadata.name,
                "",
                f"{ready}/{desired} réplicas prontas",
                kind="StatefulSet",
            )
        ]
    return []


def classify_job(job: Any) -> list[Detection]:
    failed = _cond(job, "Failed")
    if failed is not None and failed.status == "True":
        return [
            Detection(
                "JobFailed",
                job.metadata.namespace,
                job.metadata.name,
                "",
                f"{failed.reason}: {failed.message or ''}"[:200],
                kind="Job",
            )
        ]
    return []


def classify_pvc(pvc: Any, now: datetime | None = None) -> list[Detection]:
    phase = pvc.status.phase
    if phase == "Lost":
        return [
            Detection(
                "PVCLost",
                pvc.metadata.namespace,
                pvc.metadata.name,
                "",
                "volume perdido",
                kind="PersistentVolumeClaim",
                severity="crítica",
            )
        ]
    if phase == "Pending" and _age(pvc.metadata.creation_timestamp, now) > PVC_GRACE:
        sc = getattr(pvc.spec, "storage_class_name", None)
        return [
            Detection(
                "PVCPending",
                pvc.metadata.namespace,
                pvc.metadata.name,
                "",
                f"sem volume há mais de {PVC_GRACE // 60} min (storageClass={sc})",
                kind="PersistentVolumeClaim",
            )
        ]
    return []


def classify_hpa(hpa: Any) -> list[Detection]:
    cur, mx = hpa.status.current_replicas or 0, hpa.spec.max_replicas
    if mx and cur >= mx:
        return [
            Detection(
                "HPAMaxedOut",
                hpa.metadata.namespace,
                hpa.metadata.name,
                "",
                f"no máximo de réplicas ({cur}/{mx}): a carga pode estar acima da capacidade",
                kind="HorizontalPodAutoscaler",
                severity="média",
            )
        ]
    return []


def classify_event(ev: Any) -> list[Detection]:
    """Warning genérico e repetido que nenhuma regra específica cobre (FailedMount, FailedCreate…)."""
    if ev.type != "Warning" or ev.reason in COVERED_EVENT_REASONS or (ev.count or 1) < EVENT_MIN_COUNT:
        return []
    obj = ev.involved_object
    return [
        Detection(
            ev.reason or "WarningEvent",
            ev.metadata.namespace or "",
            obj.name or "",
            "",
            f"{obj.kind}: {(ev.message or '')[:180]} (x{ev.count})",
            kind=obj.kind or "Pod",
            severity="média",
        )
    ]


_UNITS = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40, "K": 1e3, "M": 1e6, "G": 1e9, "k": 1e3}


def parse_bytes(q: str) -> float:
    q = str(q).strip()
    for suf in sorted(_UNITS, key=len, reverse=True):
        if q.endswith(suf):
            return float(q[: -len(suf)]) * _UNITS[suf]
    return float(q or 0)


def classify_memory(ns: str, pod: str, container: str, usage: str, limit: str) -> list[Detection]:
    try:
        u, lim = parse_bytes(usage), parse_bytes(limit)
    except ValueError:
        return []
    if lim and u / lim >= MEMORY_NEAR_LIMIT:
        return [
            Detection(
                "MemoryNearLimit",
                ns,
                pod,
                container,
                f"usando {u / 2**20:.0f}Mi de {lim / 2**20:.0f}Mi ({u / lim:.0%}): OOM iminente",
                severity="média",
            )
        ]
    return []


# --------------------------------------------------------------------------- loop
class PodWatcher:
    def __init__(self) -> None:
        self.detections: asyncio.Queue[Detection] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._seen: dict[tuple[str, str, str], float] = {}
        self._seen_lock = threading.Lock()
        self.running = False
        self.status = "parado"
        self.last_sweep: str | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        for target, name in ((self._run, "pod-watcher"), (self._sweep_loop, "cluster-sweeper")):
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()

    def _wanted(self, namespace: str) -> bool:
        if not namespace:  # recursos de cluster (nós)
            return True
        if settings.k8s_namespaces:
            return namespace in settings.k8s_namespaces
        return namespace not in IGNORED_NAMESPACES

    def _namespaces(self) -> list[str]:
        if settings.k8s_namespaces:
            return list(settings.k8s_namespaces)
        return [
            n.metadata.name
            for n in k8s.core.list_namespace(_request_timeout=10).items
            if n.metadata.name not in IGNORED_NAMESPACES
        ]

    def _dispatch(self, det: Detection) -> None:
        key = (det.namespace, det.pod, det.type)
        now = time.monotonic()
        with self._seen_lock:
            if now - self._seen.get(key, -COOLDOWN_SECONDS) < COOLDOWN_SECONDS:
                return  # já reportado recentemente: não gasta quota de IA de novo
            self._seen[key] = now
        log.warning("anomalia detectada: %s em %s/%s (%s)", det.type, det.namespace or "-", det.pod, det.kind)
        if self._loop:
            self._loop.call_soon_threadsafe(self.detections.put_nowait, det)

    # ---- watch de pods (rápido)
    def _run(self) -> None:
        from kubernetes import watch  # import tardio: só quando há cluster

        backoff = 5
        while not self._stop.is_set():
            try:
                core = k8s.core
                w = watch.Watch()
                self.running = True
                self.status = "observando"
                backoff = 5
                for item in w.stream(core.list_pod_for_all_namespaces, timeout_seconds=60):
                    if self._stop.is_set():
                        w.stop()
                        break
                    pod = item["object"]
                    if item["type"] == "DELETED" or not self._wanted(pod.metadata.namespace):
                        continue
                    for det in classify_pod(pod):
                        self._dispatch(det)
            except K8sUnavailable as exc:
                self.running = False
                self.status = f"sem cluster: {exc}"
            except Exception as exc:  # API caiu, token expirou etc.
                self.running = False
                self.status = f"reconectando ({type(exc).__name__})"
                k8s.reset()
            if not self._stop.is_set():
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 60)
        self.running = False
        self.status = "parado"

    # ---- varredura periódica (todo o resto)
    def _sweep_loop(self) -> None:
        self._stop.wait(15)  # deixa o watch subir primeiro
        while not self._stop.is_set():
            try:
                for det in self.sweep():
                    self._dispatch(det)
                self.last_sweep = datetime.now().strftime("%H:%M:%S")
            except K8sUnavailable:
                pass
            except Exception as exc:
                log.debug("varredura falhou: %s", exc)
            self._stop.wait(SWEEP_SECONDS)

    def sweep(self) -> list[Detection]:
        """Uma passada por tudo. Cada fonte falha sozinha (RBAC, metrics-server ausente…)."""
        from kubernetes import client

        api = k8s._load()
        core, apps = k8s.core, k8s.apps
        batch, autoscaling = client.BatchV1Api(api), client.AutoscalingV2Api(api)
        out: list[Detection] = []

        def run(fn: Callable[[], list[Detection]]) -> None:
            try:
                out.extend(fn())
            except Exception as exc:
                log.debug("fonte da varredura falhou: %s", exc)

        run(lambda: [d for n in core.list_node(_request_timeout=10).items for d in classify_node(n)])
        for ns in self._namespaces():
            run(
                lambda ns=ns: [
                    d for p in core.list_namespaced_pod(ns, _request_timeout=10).items for d in classify_pod(p)
                ]
            )
            run(
                lambda ns=ns: [
                    d
                    for x in apps.list_namespaced_deployment(ns, _request_timeout=10).items
                    for d in classify_deployment(x)
                ]
            )
            run(
                lambda ns=ns: [
                    d
                    for x in apps.list_namespaced_stateful_set(ns, _request_timeout=10).items
                    for d in classify_statefulset(x)
                ]
            )
            run(
                lambda ns=ns: [
                    d for x in batch.list_namespaced_job(ns, _request_timeout=10).items for d in classify_job(x)
                ]
            )
            run(
                lambda ns=ns: [
                    d
                    for x in core.list_namespaced_persistent_volume_claim(ns, _request_timeout=10).items
                    for d in classify_pvc(x)
                ]
            )
            run(
                lambda ns=ns: [
                    d
                    for x in autoscaling.list_namespaced_horizontal_pod_autoscaler(ns, _request_timeout=10).items
                    for d in classify_hpa(x)
                ]
            )
            run(
                lambda ns=ns: [
                    d
                    for e in core.list_namespaced_event(ns, field_selector="type=Warning", _request_timeout=10).items
                    if _age(e.last_timestamp or e.event_time) < 15 * 60
                    for d in classify_event(e)
                ]
            )
            run(lambda ns=ns: self._memory(ns))
        return out

    def _memory(self, ns: str) -> list[Detection]:
        """metrics-server: uso real vs limite. Sem metrics-server, simplesmente não detecta."""
        from kubernetes import client

        metrics = client.CustomObjectsApi(k8s._load()).list_namespaced_custom_object(
            "metrics.k8s.io", "v1beta1", ns, "pods", _request_timeout=10
        )
        limits = {
            (p.metadata.name, c): v
            for p in k8s.core.list_namespaced_pod(ns, _request_timeout=10).items
            for c, v in _memory_limits(p).items()
        }
        out: list[Detection] = []
        for item in metrics.get("items", []):
            pod = item["metadata"]["name"]
            for c in item.get("containers", []):
                lim = limits.get((pod, c["name"]))
                if lim:
                    out += classify_memory(ns, pod, c["name"], c["usage"].get("memory", "0"), lim)
        return out


watcher = PodWatcher()
