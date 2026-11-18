"""Agente do Hermes Sentinel para um cluster remoto.

    SENTINEL_URL=https://sentinel.empresa SENTINEL_AGENT_TOKEN=sca_… python -m agent

Roda dentro do cluster (Helm: agent.enabled=true) ou com um kubeconfig. Usa o mesmo Monitor da central,
envia os sinais com logs e describe, e executa só as correções que um humano (ou uma política) aprovou na central.
Toda comunicação é de saída: nada fica exposto no cluster remoto.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

import httpx

from core.telemetry import setup_logging
from k8s import remediation
from k8s.client import k8s
from k8s.watcher import Detection, watcher

log = logging.getLogger("sentinel.agent")
VERSION = "1.0.0"
POLL_SECONDS = int(os.getenv("AGENT_POLL_SECONDS", "10"))
VERIFY_DELAY = int(os.getenv("VERIFY_DELAY_SECONDS", "90"))
VERIFY_ATTEMPTS = int(os.getenv("VERIFY_ATTEMPTS", "3"))
VERIFY_INTERVAL = int(os.getenv("VERIFY_INTERVAL_SECONDS", "30"))


def collect(det: Detection) -> dict:
    """Mesmo enriquecimento da central: dono, logs, describe e deploy recente."""
    owner = det.owner
    logs, events, rollout = "", "", None
    try:
        if det.kind == "Pod":
            owner = k8s.owner_deployment(det.namespace, det.pod) or owner
            logs = k8s.get_pod_logs(det.namespace, det.pod, det.container or None)
            events = k8s.describe_pod(det.namespace, det.pod)
        elif det.kind == "Node":
            events = k8s.describe_node(det.pod)
        else:
            kind = {"PersistentVolumeClaim": "pvc", "HorizontalPodAutoscaler": "hpa"}.get(det.kind, det.kind.lower())
            events = k8s.describe_resource(kind, det.namespace, det.pod)
        if owner and det.kind in ("Pod", "Deployment"):
            rollout = k8s.recent_rollout(det.namespace, owner)
    except Exception as exc:
        log.debug("coleta parcial de %s/%s: %s", det.kind, det.pod, type(exc).__name__)
    return {
        "type": det.type,
        "namespace": det.namespace,
        "pod": det.pod,
        "container": det.container,
        "reason": det.reason,
        "kind": det.kind,
        "severity": det.severity,
        "owner": owner or "",
        "logs": logs[-20000:],
        "events": events[-20000:],
        "rollout": rollout,
    }


def execute(cmd: dict) -> dict:
    """Aplica a correção e confere a saúde do alvo, como a central faria."""
    try:
        result = remediation.apply(cmd["action"], cmd["params"], cmd["namespace"], cmd["workload"], cmd["pod"])
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:2000]}
    time.sleep(VERIFY_DELAY)
    kind = remediation.health_kind(cmd["kind"], cmd["action"])
    healthy, detail = False, "não verificado"
    for _ in range(max(1, VERIFY_ATTEMPTS)):
        try:
            healthy, detail = k8s.workload_healthy(kind, cmd["namespace"], cmd["workload"])
        except Exception as exc:
            healthy, detail = False, f"verificação falhou: {type(exc).__name__}"
        if healthy:
            break
        time.sleep(VERIFY_INTERVAL)
    return {"ok": True, "result": result, "healthy": healthy, "detail": detail}


async def run() -> None:
    url = os.environ["SENTINEL_URL"].rstrip("/")
    token = os.environ["SENTINEL_AGENT_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}
    watcher.start(asyncio.get_running_loop())
    log.info("agente %s ligado à central %s", VERSION, url)
    async with httpx.AsyncClient(base_url=url, headers=headers, timeout=30) as http:
        await http.post("/api/agent/v1/heartbeat", json={"version": VERSION})
        while True:
            pending: list[Detection] = []
            while not watcher.detections.empty() and len(pending) < 50:
                pending.append(watcher.detections.get_nowait())
            try:
                if pending:
                    batch = [await asyncio.to_thread(collect, det) for det in pending]
                    (await http.post("/api/agent/v1/signals", json=batch)).raise_for_status()
                else:
                    await http.post("/api/agent/v1/heartbeat", json={"version": VERSION})
                resp = await http.get("/api/agent/v1/commands")
                resp.raise_for_status()
                for cmd in resp.json():
                    log.warning(
                        "executando %s em %s/%s (incidente %s)",
                        cmd["action"],
                        cmd["namespace"],
                        cmd["workload"],
                        cmd["incidentId"],
                    )
                    result = await asyncio.to_thread(execute, cmd)
                    await http.post(f"/api/agent/v1/commands/{cmd['id']}/result", json=result)
            except httpx.HTTPError as exc:
                log.warning("central indisponível (%s); tentando de novo", type(exc).__name__)
                for det in pending:  # não perde sinais: voltam para a fila
                    watcher.detections.put_nowait(det)
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run())
