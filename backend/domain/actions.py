"""Catálogo de ações de correção: o que existe, o risco, os parâmetros válidos e o comando equivalente.

Única fonte da verdade para o orquestrador, o servidor MCP, os prompts da IA e a autorremediação.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

QUANTITY_MEM = re.compile(r"^[1-9][0-9]{0,5}(Mi|Gi)$")
QUANTITY_CPU = re.compile(r"^([1-9][0-9]{0,4}m|[1-9][0-9]?(\.[0-9])?)$")
MAX_MEMORY_MI = 16 * 1024  # teto de 16Gi para um ajuste automático
MAX_CPU_M = 8000


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    risk: str  # baixo | médio | alto
    targets: tuple[str, ...]  # tipos de recurso em que faz sentido
    auto_eligible: bool  # pode ser liberada para autorremediação (sempre de baixo risco)
    description: str


ACTIONS: dict[str, Action] = {
    a.id: a
    for a in (
        Action(
            "rollout_restart",
            "Reiniciar o deployment",
            "baixo",
            ("Deployment", "Pod"),
            True,
            "Recria os pods com o mesmo template. Bom para falhas passageiras.",
        ),
        Action(
            "delete_pod", "Apagar o pod", "baixo", ("Pod",), True, "Remove um pod travado; o controller cria outro."
        ),
        Action(
            "rerun_job",
            "Reexecutar o job",
            "baixo",
            ("Job", "Pod"),
            True,
            "Cria um Job novo com o mesmo template (o original não roda de novo).",
        ),
        Action(
            "scale",
            "Ajustar réplicas",
            "médio",
            ("Deployment", "Pod", "HorizontalPodAutoscaler"),
            False,
            "Muda o número de réplicas (1 a 5).",
        ),
        Action(
            "rollout_undo",
            "Voltar para a revisão anterior",
            "médio",
            ("Deployment", "Pod"),
            False,
            "Desfaz o último deploy. Indicado quando a falha começou logo depois de um rollout.",
        ),
        Action(
            "set_resources",
            "Ajustar limites de CPU/memória",
            "médio",
            ("Deployment", "Pod"),
            False,
            "Muda limits/requests de um container. A correção real para OOM por limite baixo.",
        ),
        Action(
            "cordon", "Isolar o nó (cordon)", "médio", ("Node",), False, "Impede que pods novos sejam agendados no nó."
        ),
        Action(
            "drain",
            "Drenar o nó",
            "alto",
            ("Node",),
            False,
            "Isola o nó e despeja os pods (respeita PodDisruptionBudgets).",
        ),
        Action("none", "Correção manual", "baixo", (), False, "Nenhuma ação automática; seguir o runbook."),
    )
}
ACTION_IDS = tuple(ACTIONS)


class InvalidAction(ValueError):
    pass


def _mem_mi(q: str) -> int:
    return int(q[:-2]) * (1024 if q.endswith("Gi") else 1)


def _cpu_m(q: str) -> int:
    return int(q[:-1]) if q.endswith("m") else int(float(q) * 1000)


def validate(action: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Valida e normaliza os parâmetros. Erro = a ação não vira pedido de aprovação."""
    if action not in ACTIONS:
        raise InvalidAction(f"ação desconhecida: {action}")
    p = dict(params or {})
    if action == "scale":
        replicas = int(p.get("replicas") or 0)
        if not 1 <= replicas <= 5:
            raise InvalidAction("scale exige replicas entre 1 e 5")
        return {"replicas": replicas}
    if action == "set_resources":
        container = str(p.get("container") or "").strip()
        if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", container):
            raise InvalidAction("set_resources exige o nome do container")
        out: dict[str, Any] = {"container": container}
        mem, cpu = p.get("memory_limit"), p.get("cpu_limit")
        if not mem and not cpu:
            raise InvalidAction("informe memory_limit (ex.: 256Mi) e/ou cpu_limit (ex.: 500m)")
        if mem:
            if not QUANTITY_MEM.match(str(mem)) or _mem_mi(str(mem)) > MAX_MEMORY_MI:
                raise InvalidAction("memory_limit inválido: use Mi/Gi, até 16Gi")
            out["memory_limit"] = str(mem)
        if cpu:
            if not QUANTITY_CPU.match(str(cpu)) or _cpu_m(str(cpu)) > MAX_CPU_M:
                raise InvalidAction("cpu_limit inválido: use m ou núcleos, até 8")
            out["cpu_limit"] = str(cpu)
        return out
    return {}


def command(action: str, *, namespace: str, workload: str, pod: str, kind: str, params: dict[str, Any]) -> str:
    """Comando kubectl equivalente, mostrado ao operador antes de aprovar."""
    ns = f"-n {namespace}"
    if action == "rollout_restart":
        return f"kubectl rollout restart deployment/{workload} {ns}"
    if action == "scale":
        return f"kubectl scale deployment/{workload} --replicas={params['replicas']} {ns}"
    if action == "delete_pod":
        return f"kubectl delete pod {pod} {ns}"
    if action == "rollout_undo":
        return f"kubectl rollout undo deployment/{workload} {ns}"
    if action == "set_resources":
        lim = ",".join(f"{k.split('_')[0]}={v}" for k, v in params.items() if k.endswith("_limit"))
        return f"kubectl set resources deployment/{workload} -c {params['container']} --limits={lim} {ns}"
    if action == "cordon":
        return f"kubectl cordon {workload}"
    if action == "drain":
        return f"kubectl drain {workload} --ignore-daemonsets --delete-emptydir-data"
    if action == "rerun_job":
        return f"kubectl create job {workload}-rerun --from=job/{workload} {ns}  (cópia do template)"
    return "(nenhuma ação automática; correção manual recomendada)"


def catalog_for_prompt() -> str:
    """Texto curto para os prompts da IA."""
    return "\n".join(f"- {a.id} (risco {a.risk}): {a.description}" for a in ACTIONS.values())
