"""Acesso ao Kubernetes local (~/.kube/config). Tudo síncrono — chame via asyncio.to_thread."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from config import settings

log = logging.getLogger("sentinel.k8s")

try:
    from kubernetes import client
    from kubernetes import config as k8s_config
    from kubernetes.client.rest import ApiException
except ImportError:  # pragma: no cover - dependência obrigatória, mas não derruba o app
    client = None  # type: ignore[assignment]
    k8s_config = None  # type: ignore[assignment]
    ApiException = Exception  # type: ignore[assignment,misc]


class K8sUnavailable(RuntimeError):
    pass


class K8sService:
    def __init__(self) -> None:
        self._api_client: Any = None
        self.context: str | None = None
        self.last_error: str | None = None

    # ------------------------------------------------------------------ conexão
    def _load(self) -> Any:
        if self._api_client is not None:
            return self._api_client
        if client is None:
            raise K8sUnavailable("pacote 'kubernetes' não instalado")
        path = settings.kubeconfig_path
        if not path.is_file():
            raise K8sUnavailable(f"kubeconfig não encontrado em {path}")
        try:
            _contexts, active = k8s_config.list_kube_config_contexts(config_file=str(path))
            self.context = (active or {}).get("name")
            self._api_client = k8s_config.new_client_from_config(config_file=str(path))
        except Exception as exc:
            raise K8sUnavailable(f"kubeconfig inválido: {exc}") from exc
        return self._api_client

    def reset(self) -> None:
        self._api_client = None

    @property
    def core(self) -> Any:
        return client.CoreV1Api(self._load())

    @property
    def apps(self) -> Any:
        return client.AppsV1Api(self._load())

    def check(self) -> dict[str, Any]:
        """Health check barato: versão do API server com timeout curto."""
        try:
            version = client.VersionApi(self._load()).get_code(_request_timeout=4)
            nodes = self.core.list_node(_request_timeout=4).items
            self.last_error = None
            return {
                "ok": True,
                "context": self.context,
                "version": version.git_version,
                "nodes": len(nodes),
                "detail": f"{self.context} · {version.git_version} · {len(nodes)} nó(s)",
            }
        except K8sUnavailable as exc:
            self.last_error = str(exc)
            return {"ok": False, "context": None, "detail": str(exc)}
        except Exception as exc:
            self.reset()
            self.last_error = f"API server inacessível: {type(exc).__name__}"
            return {"ok": False, "context": self.context, "detail": self.last_error}

    # ------------------------------------------------------------------ leitura
    def get_pod_logs(self, namespace: str, pod: str, container: str | None = None, tail: int | None = None) -> str:
        """Últimas N linhas (padrão 80). Tenta primeiro o container anterior (quem caiu)."""
        tail = tail or settings.k8s_log_tail_lines
        for previous in (True, False):
            try:
                text = self.core.read_namespaced_pod_log(
                    pod, namespace, container=container, tail_lines=tail, previous=previous, _request_timeout=10
                )
                if text:
                    lines = text.splitlines()[-tail:]
                    return "\n".join(lines)
            except ApiException:
                continue
        return "(sem logs disponíveis)"

    def describe_pod(self, namespace: str, pod: str) -> str:
        """Resumo no estilo `kubectl describe pod`: estado dos containers, limites e eventos."""
        p = self.core.read_namespaced_pod(pod, namespace, _request_timeout=10)
        out = [f"Pod: {namespace}/{pod}", f"Node: {p.spec.node_name}", f"Phase: {p.status.phase}"]
        for c in p.spec.containers:
            res = c.resources
            out.append(
                f"Container {c.name}: image={c.image} "
                f"limits={getattr(res, 'limits', None)} requests={getattr(res, 'requests', None)}"
            )
        for cs in p.status.container_statuses or []:
            state = cs.state
            last = cs.last_state
            out.append(
                f"  {cs.name}: ready={cs.ready} restarts={cs.restart_count} "
                f"waiting={getattr(state.waiting, 'reason', None)} "
                f"lastTerminated={getattr(last.terminated, 'reason', None)} "
                f"exitCode={getattr(last.terminated, 'exit_code', None)}"
            )
        try:
            events = self.core.list_namespaced_event(
                namespace, field_selector=f"involvedObject.name={pod}", _request_timeout=10
            ).items
            events.sort(key=lambda e: e.last_timestamp or e.event_time or datetime.min.replace(tzinfo=UTC))
            out.append("Events:")
            for e in events[-15:]:
                out.append(f"  {e.type} {e.reason} (x{e.count or 1}): {e.message}")
        except ApiException as exc:
            out.append(f"Events: indisponível ({exc.status})")
        return "\n".join(out)

    def owner_deployment(self, namespace: str, pod: str) -> str | None:
        """Pod → ReplicaSet → Deployment."""
        try:
            p = self.core.read_namespaced_pod(pod, namespace, _request_timeout=10)
            for ref in p.metadata.owner_references or []:
                if ref.kind == "ReplicaSet":
                    rs = self.apps.read_namespaced_replica_set(ref.name, namespace, _request_timeout=10)
                    for rref in rs.metadata.owner_references or []:
                        if rref.kind == "Deployment":
                            return rref.name
                if ref.kind in ("StatefulSet", "Deployment", "DaemonSet", "Job"):
                    return ref.name
        except ApiException:
            return None
        return None

    def first_pod_of(self, namespace: str, deployment: str) -> str | None:
        try:
            pods = self.core.list_namespaced_pod(
                namespace, label_selector=f"app={deployment}", _request_timeout=10
            ).items
            return pods[0].metadata.name if pods else None
        except Exception:
            return None

    # ------------------------------------------------------------------ leitura ampla (ferramentas do Hermes)
    def _client(self, name: str) -> Any:
        return getattr(client, name)(self._load())

    @staticmethod
    def _ev_line(e: Any) -> str:
        when = e.last_timestamp or e.event_time
        obj = e.involved_object
        return (
            f"{when:%H:%M:%S} " if when else ""
        ) + f"{e.type} {e.reason} {obj.kind}/{obj.name} (x{e.count or 1}): {e.message}"

    def list_events(self, namespace: str, warnings_only: bool = True, obj_name: str = "", limit: int = 30) -> str:
        sel = ["type=Warning"] if warnings_only else []
        if obj_name:
            sel.append(f"involvedObject.name={obj_name}")
        items = self.core.list_namespaced_event(
            namespace, field_selector=",".join(sel) or None, _request_timeout=10
        ).items
        epoch = datetime.min.replace(tzinfo=UTC)
        items.sort(key=lambda e: e.last_timestamp or e.event_time or epoch)
        return "\n".join(self._ev_line(e) for e in items[-limit:]) or "(nenhum evento)"

    def describe_resource(self, kind: str, namespace: str, name: str) -> str:
        """Resumo de deployment/statefulset/daemonset/job/cronjob/pvc/service/hpa/configmap (só as CHAVES)."""
        kind = kind.lower()
        out: list[str] = [f"{kind}: {namespace}/{name}"]
        if kind in ("deployment", "statefulset", "daemonset"):
            apps = self.apps
            obj = {
                "deployment": apps.read_namespaced_deployment,
                "statefulset": apps.read_namespaced_stateful_set,
                "daemonset": apps.read_namespaced_daemon_set,
            }[kind](name, namespace, _request_timeout=10)
            st = obj.status
            out.append(
                f"replicas: desejadas={getattr(obj.spec, 'replicas', None)} prontas={getattr(st, 'ready_replicas', None)} "
                f"disponíveis={getattr(st, 'available_replicas', None)} atualizadas={getattr(st, 'updated_replicas', None)}"
            )
            if getattr(obj.spec, "strategy", None):
                out.append(f"estratégia: {obj.spec.strategy.type}")
            for c in obj.spec.template.spec.containers:
                probes = [n for n in ("liveness_probe", "readiness_probe", "startup_probe") if getattr(c, n, None)]
                env_from = [getattr(e.config_map_ref or e.secret_ref, "name", "?") for e in (c.env_from or [])]
                out.append(
                    f"container {c.name}: image={c.image} limits={getattr(c.resources, 'limits', None)} "
                    f"requests={getattr(c.resources, 'requests', None)} probes={probes} envFrom={env_from}"
                )
            vols = [
                f"{v.name}:{'pvc=' + v.persistent_volume_claim.claim_name if v.persistent_volume_claim else 'cm/secret/outro'}"
                for v in (obj.spec.template.spec.volumes or [])
            ]
            if vols:
                out.append(f"volumes: {vols}")
            for c in getattr(st, "conditions", None) or []:
                out.append(f"condição {c.type}={c.status} {c.reason or ''}: {c.message or ''}")
        elif kind == "job":
            obj = self._client("BatchV1Api").read_namespaced_job(name, namespace, _request_timeout=10)
            st = obj.status
            out.append(
                f"ativos={st.active} sucesso={st.succeeded} falhas={st.failed} backoffLimit={obj.spec.backoff_limit}"
            )
            for c in st.conditions or []:
                out.append(f"condição {c.type}={c.status} {c.reason or ''}: {c.message or ''}")
        elif kind == "cronjob":
            obj = self._client("BatchV1Api").read_namespaced_cron_job(name, namespace, _request_timeout=10)
            out.append(
                f"schedule={obj.spec.schedule} suspenso={obj.spec.suspend} "
                f"último={obj.status.last_schedule_time} últimoSucesso={getattr(obj.status, 'last_successful_time', None)}"
            )
        elif kind in ("pvc", "persistentvolumeclaim"):
            obj = self.core.read_namespaced_persistent_volume_claim(name, namespace, _request_timeout=10)
            out.append(
                f"fase={obj.status.phase} storageClass={obj.spec.storage_class_name} "
                f"pedido={obj.spec.resources.requests} capacidade={obj.status.capacity} volume={obj.spec.volume_name}"
            )
        elif kind in ("service", "svc"):
            obj = self.core.read_namespaced_service(name, namespace, _request_timeout=10)
            out.append(
                f"tipo={obj.spec.type} selector={obj.spec.selector} portas="
                f"{[(p.port, p.target_port) for p in obj.spec.ports or []]}"
            )
            try:
                ep = self.core.read_namespaced_endpoints(name, namespace, _request_timeout=10)
                ready = sum(len(s.addresses or []) for s in ep.subsets or [])
                notready = sum(len(s.not_ready_addresses or []) for s in ep.subsets or [])
                out.append(
                    f"endpoints: prontos={ready} não-prontos={notready}" + (" ← SEM BACKEND" if not ready else "")
                )
            except Exception:
                out.append("endpoints: (nenhum)")
        elif kind in ("hpa", "horizontalpodautoscaler"):
            obj = self._client("AutoscalingV2Api").read_namespaced_horizontal_pod_autoscaler(
                name, namespace, _request_timeout=10
            )
            out.append(
                f"min={obj.spec.min_replicas} max={obj.spec.max_replicas} atual={obj.status.current_replicas} "
                f"desejado={obj.status.desired_replicas}"
            )
            for c in obj.status.conditions or []:
                out.append(f"condição {c.type}={c.status} {c.reason or ''}: {c.message or ''}")
        elif kind in ("configmap", "cm"):
            obj = self.core.read_namespaced_config_map(name, namespace, _request_timeout=10)
            out.append(f"chaves: {sorted((obj.data or {}).keys())} (valores não são mostrados)")
        else:
            raise ValueError(f"tipo não suportado: {kind}")
        try:
            out.append("eventos:\n" + self.list_events(namespace, warnings_only=False, obj_name=name, limit=10))
        except Exception as exc:  # eventos são complemento: o describe sai sem eles
            log.debug("eventos de %s/%s indisponíveis: %s", namespace, name, exc)
        return "\n".join(out)

    def describe_node(self, name: str) -> str:
        n = self.core.read_node(name, _request_timeout=10)
        out = [
            f"Node: {name}",
            f"kubelet={n.status.node_info.kubelet_version} os={n.status.node_info.os_image}",
            f"capacidade={n.status.capacity}",
            f"alocável={n.status.allocatable}",
            f"unschedulable={bool(n.spec.unschedulable)} taints={[(t.key, t.effect) for t in n.spec.taints or []]}",
        ]
        for c in n.status.conditions or []:
            out.append(f"condição {c.type}={c.status} {c.reason or ''}: {c.message or ''}")
        try:
            from kubernetes import client as kc

            m = kc.CustomObjectsApi(self._load()).get_cluster_custom_object(
                "metrics.k8s.io", "v1beta1", "nodes", name, _request_timeout=10
            )
            out.append(f"uso agora: cpu={m['usage']['cpu']} memória={m['usage']['memory']}")
        except Exception:
            out.append("uso agora: (metrics-server indisponível)")
        return "\n".join(out)

    def namespace_overview(self, namespace: str) -> str:
        out = [f"Namespace {namespace}"]
        for d in self.apps.list_namespaced_deployment(namespace, _request_timeout=10).items:
            out.append(f"deployment/{d.metadata.name}: {d.status.ready_replicas or 0}/{d.spec.replicas} prontas")
        for s in self.apps.list_namespaced_stateful_set(namespace, _request_timeout=10).items:
            out.append(f"statefulset/{s.metadata.name}: {s.status.ready_replicas or 0}/{s.spec.replicas} prontas")
        for j in self._client("BatchV1Api").list_namespaced_job(namespace, _request_timeout=10).items:
            out.append(f"job/{j.metadata.name}: sucesso={j.status.succeeded or 0} falhas={j.status.failed or 0}")
        for p in self.core.list_namespaced_persistent_volume_claim(namespace, _request_timeout=10).items:
            out.append(f"pvc/{p.metadata.name}: {p.status.phase} ({p.spec.storage_class_name})")
        for h in (
            self._client("AutoscalingV2Api")
            .list_namespaced_horizontal_pod_autoscaler(namespace, _request_timeout=10)
            .items
        ):
            out.append(
                f"hpa/{h.metadata.name}: {h.status.current_replicas}/{h.spec.max_replicas} (min {h.spec.min_replicas})"
            )
        for sv in self.core.list_namespaced_service(namespace, _request_timeout=10).items:
            out.append(f"service/{sv.metadata.name}: {sv.spec.type}")
        return "\n".join(out)

    def resource_usage(self, namespace: str) -> str:
        """Uso real (metrics-server) comparado aos limites de cada container."""
        from kubernetes import client as kc

        metrics = kc.CustomObjectsApi(self._load()).list_namespaced_custom_object(
            "metrics.k8s.io", "v1beta1", namespace, "pods", _request_timeout=10
        )
        limits: dict[tuple[str, str], Any] = {}
        for p in self.core.list_namespaced_pod(namespace, _request_timeout=10).items:
            for c in p.spec.containers:
                limits[(p.metadata.name, c.name)] = getattr(c.resources, "limits", None) or {}
        out = []
        for item in metrics.get("items", []):
            for c in item.get("containers", []):
                lim = limits.get((item["metadata"]["name"], c["name"]), {})
                out.append(
                    f"{item['metadata']['name']}/{c['name']}: cpu={c['usage'].get('cpu')} (limite {lim.get('cpu', '-')}) "
                    f"memória={c['usage'].get('memory')} (limite {lim.get('memory', '-')})"
                )
        return "\n".join(out) or "(sem métricas)"

    # ------------------------------------------------------------------ remediação (exige aprovação)
    def rollout_restart(self, namespace: str, deployment: str) -> str:
        stamp = datetime.now(UTC).isoformat()
        body = {"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": stamp}}}}}
        self.apps.patch_namespaced_deployment(deployment, namespace, body, _request_timeout=10)
        return f"deployment/{deployment} reiniciado (restartedAt={stamp})"

    def scale(self, namespace: str, deployment: str, replicas: int) -> str:
        self.apps.patch_namespaced_deployment_scale(
            deployment, namespace, {"spec": {"replicas": int(replicas)}}, _request_timeout=10
        )
        return f"deployment/{deployment} escalado para {replicas} réplica(s)"

    def delete_pod(self, namespace: str, pod: str) -> str:
        self.core.delete_namespaced_pod(pod, namespace, _request_timeout=10)
        return f"pod/{pod} removido (o controller recria)"


k8s = K8sService()
