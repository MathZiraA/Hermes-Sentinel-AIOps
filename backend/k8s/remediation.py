"""Executa uma ação do catálogo no cluster e confere a saúde do alvo. Usado pela central e pelo agente."""

from __future__ import annotations

from typing import Any

from k8s.client import k8s


def apply(action: str, params: dict[str, Any], namespace: str, workload: str, pod: str) -> str:
    """Síncrono (chame em thread). A ação e os parâmetros já foram validados por domain.actions."""
    p = params or {}
    handlers = {
        "rollout_restart": lambda: k8s.rollout_restart(namespace, workload),
        "scale": lambda: k8s.scale(namespace, workload, int(p["replicas"])),
        "delete_pod": lambda: k8s.delete_pod(namespace, pod),
        "rollout_undo": lambda: k8s.rollout_undo(namespace, workload),
        "set_resources": lambda: k8s.set_resources(
            namespace,
            workload,
            p["container"],
            {k.split("_")[0]: v for k, v in p.items() if k in ("memory_limit", "cpu_limit")},
        ),
        "cordon": lambda: k8s.cordon(workload),
        "drain": lambda: k8s.drain(workload),
        "rerun_job": lambda: k8s.rerun_job(namespace, workload),
    }
    if action not in handlers:
        raise ValueError(f"ação sem execução automática: {action}")
    return handlers[action]()


def health_kind(resource_kind: str, action: str) -> str:
    """Que tipo de recurso conferir depois da correção."""
    if resource_kind == "Node":
        return "node"
    if action == "rerun_job":
        return "job"
    if resource_kind in ("StatefulSet", "Deployment"):
        return resource_kind.lower()
    return "deployment"
