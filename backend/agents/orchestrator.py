"""Fluxo de incidente: Monitor → Supervisor → Investigator (Hermes) → Executor (aprovação) → ITSM."""

from __future__ import annotations

import asyncio
import logging
import random
import string
from datetime import datetime

from agents.base import executor, investigator, itsm, monitor, supervisor
from config import settings
from core.bus import bus
from db import repository as repo
from domain.lifecycle import OPEN, check_transition, severity_for
from integrations import brain, obsidian
from integrations.github_itsm import create_issue, github_configured
from integrations.hermes_client import hermes, tail_lines
from k8s.client import K8sUnavailable, k8s
from k8s.watcher import Detection, watcher
from mcp_server import tool_calls as mcp_tool_calls
from schemas.events import ApprovalRequest, Incident, KanbanAction, SimulateRequest, now_iso

log = logging.getLogger("sentinel.orchestrator")

STEP = 1.8  # pausa entre etapas: tempo para a caminhada/animação na UI


def _new_id() -> str:
    # IDs legíveis, não segredos: `random` basta (S311 não se aplica)
    return "INC-" + datetime.now().strftime("%H%M%S") + "-" + "".join(random.choices(string.ascii_uppercase, k=3))  # noqa: S311


# --------------------------------------------------------------------------- dados simulados
def _simulated_payload(req: SimulateRequest) -> tuple[str, str, str, str]:
    """Dados realistas de um pod do StockFlow para cada tipo de incidente. Devolve (pod, logs, describe, reason)."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))  # noqa: S311 (nome fictício)
    pod = f"{req.deployment}-7d9f8c6b5-{suffix}"
    if req.type == "OOMKilled":
        logs = "\n".join(
            [
                "2026-11-17 19:02:11.402  INFO 1 --- [main] o.s.b.w.e.tomcat.TomcatWebServer : Tomcat started on port(s): 8080",
                "2026-11-17 19:02:11.877  INFO 1 --- [main] b.c.a.pedidos.PedidosApplication : Started PedidosApplication in 38.2 seconds",
                *[
                    f"2026-11-17 19:04:{10 + i:02d}.120  WARN 1 --- [nio-8080-exec-{i}] b.c.a.pedidos.service.RelatorioService : carregando lote {i * 5000} pedidos em memória"
                    for i in range(1, 9)
                ],
                "2026-11-17 19:04:19.981  WARN 1 --- [GC] jvm : GC overhead limit approaching (heap 301M/307M)",
                'Exception in thread "http-nio-8080-exec-7" java.lang.OutOfMemoryError: Java heap space',
                "\tat java.base/java.util.Arrays.copyOf(Arrays.java:3512)",
                "\tat b.c.a.pedidos.service.RelatorioService.gerarRelatorioCompleto(RelatorioService.java:88)",
            ]
        )
        events = (
            f"Pod: {req.namespace}/{pod}\nContainer {req.deployment}: limits={{'memory': '512Mi'}} requests={{'cpu': '250m', 'memory': '300Mi'}}\n"
            f"  {req.deployment}: ready=False restarts=3 waiting=CrashLoopBackOff lastTerminated=OOMKilled exitCode=137\n"
            "Events:\n  Warning BackOff (x6): Back-off restarting failed container\n  Normal Killing (x3): Container exceeded memory limit"
        )
        reason = "exit 137 · restarts=3"
    elif req.type == "CrashLoopBackOff":
        logs = "\n".join(
            [
                "2026-11-17 19:06:01.010  INFO 1 --- [main] b.c.a.pedidos.PedidosApplication : Starting PedidosApplication",
                "2026-11-17 19:06:09.552  INFO 1 --- [main] com.zaxxer.hikari.HikariDataSource : HikariPool-1 - Starting...",
                "2026-11-17 19:06:39.601 ERROR 1 --- [main] com.zaxxer.hikari.pool.HikariPool : HikariPool-1 - Exception during pool initialization.",
                "com.mysql.cj.jdbc.exceptions.CommunicationsException: Communications link failure",
                "Caused by: java.net.ConnectException: Connection refused (mysql:3306)",
                "2026-11-17 19:06:39.890 ERROR 1 --- [main] o.s.boot.SpringApplication : Application run failed",
            ]
        )
        events = (
            f"Pod: {req.namespace}/{pod}\n  {req.deployment}: ready=False restarts=5 waiting=CrashLoopBackOff lastTerminated=Error exitCode=1\n"
            "Events:\n  Warning BackOff (x9): Back-off restarting failed container\n"
            f'  Warning Unhealthy (x2): Readiness probe failed: Get "http://10.244.0.17:8080/{req.deployment}/porta": connection refused'
        )
        reason = "back-off restarting failed container"
    else:
        logs = "(container nunca iniciou: sem logs)"
        events = (
            f"Pod: {req.namespace}/{pod}\n  {req.deployment}: ready=False restarts=0 waiting=ImagePullBackOff\n"
            f'Events:\n  Warning Failed (x4): Failed to pull image "leonardosartorello/java-{req.deployment}-k8s:v9": not found\n'
            "  Normal BackOff (x7): Back-off pulling image"
        )
        reason = "Back-off pulling image"
    return pod, logs, events, reason


class Orchestrator:
    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self.timelines: dict[str, list[str]] = {}
        self._tasks: set[asyncio.Task] = set()
        self._comm_lock = asyncio.Lock()

    def _spawn(self, coro) -> asyncio.Task:  # type: ignore[no-untyped-def]
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _mark(self, inc: Incident, text: str, actor: str = "sistema", kind: str = "note") -> None:
        """Linha do tempo: memória (post-mortem) + banco (persistente)."""
        self.timelines.setdefault(inc.id, []).append(f"{datetime.now().strftime('%H:%M:%S')}: {text}")
        try:
            await repo.add_event(inc.id, text, actor=actor, kind=kind)
        except Exception as exc:  # o fluxo nunca para por causa do banco
            log.warning("linha do tempo não gravada (%s): %s", inc.id, type(exc).__name__)

    async def _save(self, inc: Incident) -> None:
        try:
            await repo.save_incident(inc)
        except Exception as exc:
            log.warning("incidente %s não gravado: %s", inc.id, type(exc).__name__)

    async def _set_status(self, inc: Incident, new: str, actor: str = "sistema") -> None:
        """Muda o status respeitando o ciclo de vida (domain.lifecycle) e persiste."""
        old = inc.status
        check_transition(old, new)
        inc.status = new  # type: ignore[assignment]
        if new in ("resolved", "closed", "failed") and not inc.resolvedAt:
            inc.resolvedAt = now_iso()
        if old != new:
            await self._mark(inc, f"status: {old} → {new}", actor=actor, kind="status")
        await self._save(inc)

    async def _register(self, inc: Incident) -> None:
        """Primeira gravação: cluster, severidade e cache em memória."""
        inc.cluster = inc.cluster if inc.cluster != "local" else settings.cluster_id
        inc.sev = severity_for(inc.type, inc.severity)
        self.incidents[inc.id] = inc
        await self._save(inc)

    @property
    def pending_approvals(self) -> list[dict]:
        return [
            i.approval.model_dump() for i in self.incidents.values() if i.status == "waiting_approval" and i.approval
        ]

    # ------------------------------------------------------------------ entrada: watcher real
    def _open_for(self, namespace: str, target: str) -> Incident | None:
        """Incidente ainda aberto para o mesmo workload: sinais novos se juntam a ele (1 incidente, não 5)."""
        for inc in reversed(list(self.incidents.values())):
            if inc.namespace == namespace and (inc.deployment or inc.pod) == target and inc.status in OPEN:
                return inc
        return None

    async def _collect(self, det: Detection) -> tuple[str | None, str, str]:
        """(workload dono, logs, describe) conforme o tipo de recurso."""
        if det.kind == "Pod":
            deployment = await asyncio.to_thread(k8s.owner_deployment, det.namespace, det.pod)
            logs = await asyncio.to_thread(k8s.get_pod_logs, det.namespace, det.pod, det.container or None)
            events = await asyncio.to_thread(k8s.describe_pod, det.namespace, det.pod)
            return deployment, logs, events
        if det.kind == "Node":
            return None, "(nó: sem logs de container)", await asyncio.to_thread(k8s.describe_node, det.pod)
        kind = {"PersistentVolumeClaim": "pvc", "HorizontalPodAutoscaler": "hpa"}.get(det.kind, det.kind.lower())
        try:
            text = await asyncio.to_thread(k8s.describe_resource, kind, det.namespace, det.pod)
        except Exception:
            text = await asyncio.to_thread(k8s.list_events, det.namespace, True, det.pod)
        owner = det.pod if det.kind in ("Deployment", "StatefulSet", "DaemonSet", "Job") else None
        return owner, "(recurso sem logs de container)", text

    async def consume_detections(self) -> None:
        while True:
            det: Detection = await watcher.detections.get()
            try:
                deployment, logs, events = await self._collect(det)
            except Exception as exc:
                log.warning("falha coletando dados de %s/%s: %s", det.kind, det.pod, type(exc).__name__)
                if det.kind == "Pod" and getattr(exc, "status", None) == 404:
                    continue  # o pod sumiu entre a detecção e a coleta: nada a investigar
                deployment, logs, events = None, "(indisponível)", f"(describe falhou: {type(exc).__name__})"
            deployment = deployment or det.owner or None
            target = deployment or det.pod
            existing = self._open_for(det.namespace, target)
            if existing:
                signal = f"{det.type} em {det.kind}/{det.pod}: {det.reason}"
                if signal not in existing.related:
                    existing.related.append(signal)
                    await self._mark(existing, f"Sinal correlacionado: {signal}")
                    await monitor.emit(
                        "monitoring", f"Mais um sinal em {target}: {det.type}.", incident_id=existing.id, log=signal
                    )
                continue
            inc = Incident(
                id=_new_id(),
                type=det.type,
                namespace=det.namespace,
                pod=det.pod,
                container=det.container,
                deployment=deployment,
                reason=det.reason,
                resourceKind=det.kind,
                severity=det.severity,
                logs=tail_lines(logs),
                events=events,
                simulated=False,
            )
            self._spawn(self.run_incident(inc, use_ai=True))

    # ------------------------------------------------------------------ entrada: simulação
    def simulate(self, req: SimulateRequest) -> Incident:
        pod, logs, events, reason = _simulated_payload(req)
        inc = Incident(
            id=_new_id(),
            type=req.type,
            namespace=req.namespace,
            pod=pod,
            container=req.deployment,
            deployment=req.deployment,
            reason=reason,
            logs=logs,
            events=events,
            simulated=True,
        )
        self._spawn(self.run_incident(inc, use_ai=req.useAi))
        return inc

    # ------------------------------------------------------------------ fluxo principal
    async def run_incident(self, inc: Incident, use_ai: bool) -> None:
        await self._register(inc)
        tag = " (simulado)" if inc.simulated else ""
        target = inc.deployment or inc.pod
        card = lambda **kw: KanbanAction(cardId=inc.id, **kw)  # noqa: E731

        # 1. Monitor detecta (determinístico)
        await self._mark(inc, f"Monitor detectou {inc.type} em {inc.namespace}/{inc.pod}{tag}")
        await monitor.emit(
            "alert",
            f"Alerta! {inc.type} em {target}{tag}",
            incident_id=inc.id,
            log=f"{inc.type} {inc.namespace}/{inc.pod} container={inc.container} :: {inc.reason}",
        )
        await asyncio.sleep(STEP)

        # 2. Supervisor vai até o Monitor e abre o incidente
        await supervisor.walk("AGENT_FACTORY", "Indo verificar o alerta…", incident_id=inc.id)
        await asyncio.sleep(STEP)
        await supervisor.emit(
            "talking",
            f"Incidente aberto: {target} instável. Equipe acionada.",
            zone="AGENT_FACTORY",
            incident_id=inc.id,
        )
        await itsm.walk(
            "KANBAN_WALL",
            "Registrando no Kanban…",
            incident_id=inc.id,
            kanban=card(
                op="create", title=f"{inc.type}: {inc.namespace}/{target}", column="Backlog", agentId="itsm", progress=5
            ),
        )
        await self._mark(inc, "Supervisor abriu o incidente; ITSM criou o card no Kanban")
        await asyncio.sleep(STEP)
        await monitor.emit("monitoring", "De olho no restante do cluster.", incident_id=inc.id)

        # 3. Investigator: logs + describe + runbooks → Hermes (1 chamada) ou fallback
        await self._set_status(inc, "investigating")
        await supervisor.walk("CENTRAL_HUB", "Investigator, preciso da causa raiz.", incident_id=inc.id)
        await investigator.emit(
            "investigating",
            f"Lendo as últimas {settings.k8s_log_tail_lines} linhas de log…",
            incident_id=inc.id,
            log=tail_lines(inc.logs, 12),
            kanban=card(op="move", column="Investigando", agentId="investigator", progress=25),
        )
        await itsm.go_home()
        runbooks = await asyncio.to_thread(obsidian.find_runbooks, inc.type)
        inc.memory = await asyncio.to_thread(brain.related, inc.type, target, inc.resourceKind)
        if inc.memory:
            await self._mark(inc, "Investigator consultou o Hermes Brain (casos e lições anteriores)")
            await investigator.emit(
                "investigating", "Lembrando casos parecidos no Hermes Brain…", incident_id=inc.id, log=inc.memory[:600]
            )
        await asyncio.sleep(STEP)
        await investigator.emit(
            "thinking",
            "Consultando o Hermes…" if use_ai else "Cruzando com os runbooks (modo demo, sem IA)…",
            incident_id=inc.id,
            log=f"runbooks: {', '.join(n for n, _ in runbooks) or 'nenhum'} | IA: {'sim' if use_ai else 'não'}",
        )
        if use_ai and not inc.simulated:
            # Hermes (VPS) investiga sozinho pelas ferramentas MCP; pod simulado não existe no cluster
            rca = await hermes.investigate(inc, runbooks)
            calls = len(mcp_tool_calls.pop(inc.id, []))
            if rca.get("source") == "hermes-agent+mcp":
                await self._mark(inc, f"Hermes investigou pelo MCP ({calls} chamada(s) de ferramenta)")
        elif use_ai:
            rca = await hermes.diagnose(inc, runbooks)
        else:
            from integrations.hermes_client import fallback_rca

            rca = fallback_rca(inc, runbooks, "simulação sem IA (economiza quota)")
        inc.rca = rca
        if rca.get("source") == "fallback" and use_ai:
            await investigator.emit(
                "thinking",
                "IA ocupada (quota). Usando o runbook local.",
                incident_id=inc.id,
                log=rca.get("fallbackReason", ""),
            )
            await asyncio.sleep(STEP / 2)
        await self._mark(inc, f"RCA ({rca.get('source')}): {rca.get('rootCause')}")
        await investigator.emit(
            "talking",
            f"Causa: {rca.get('rootCause', '')}",
            incident_id=inc.id,
            log="\n".join(rca.get("evidence", [])[:4]),
            kanban=card(op="update", progress=50),
        )
        await asyncio.sleep(STEP)

        # 4. Supervisor traduz para stakeholders
        await supervisor.emit(
            "talking",
            rca.get("stakeholderSummary") or "Encontramos a causa. Preparando a correção.",
            incident_id=inc.id,
        )
        await asyncio.sleep(STEP)

        # 5. Executor prepara o comando e PARA aguardando aprovação humana
        await investigator.go_home()
        await self._request_approval(inc, rca)

    async def _request_approval(self, inc: Incident, rca: dict) -> None:
        card = lambda **kw: KanbanAction(cardId=inc.id, **kw)  # noqa: E731
        action = (rca.get("recommendedAction") or {}).get("type", "rollout_restart")
        replicas = (rca.get("recommendedAction") or {}).get("replicas") or 2
        cmd = {
            "rollout_restart": f"kubectl rollout restart deployment/{inc.deployment or inc.pod} -n {inc.namespace}",
            "scale": f"kubectl scale deployment/{inc.deployment or inc.pod} --replicas={replicas} -n {inc.namespace}",
            "delete_pod": f"kubectl delete pod {inc.pod} -n {inc.namespace}",
            "none": "(nenhuma ação automática; correção manual recomendada)",
        }[action if action in ("rollout_restart", "scale", "delete_pod", "none") else "rollout_restart"]
        inc.approval = ApprovalRequest(
            incidentId=inc.id,
            action=action,
            command=cmd,
            target=f"{inc.namespace}/{inc.deployment or inc.pod}",
            description=(rca.get("recommendedAction") or {}).get("reason") or rca.get("rootCause", ""),
            risk="baixo" if action in ("rollout_restart", "delete_pod") else "médio",
            simulated=inc.simulated,
        )
        await self._set_status(inc, "waiting_approval")
        await executor.emit(
            "waiting_approval",
            "Correção pronta. Aguardando sua aprovação.",
            incident_id=inc.id,
            log=cmd,
            approval=inc.approval,
            kanban=card(op="move", column="Aguardando aprovação", agentId="executor", progress=65),
        )
        await supervisor.go_home("idle", "Aguardando aprovação humana para corrigir.")
        await self._mark(inc, f"Executor aguardando aprovação: {cmd}")

    # ------------------------------------------------------------------ entrada: proposta do Hermes (chat/MCP)
    async def propose_from_hermes(
        self,
        *,
        namespace: str,
        deployment: str,
        action: str,
        root_cause: str,
        summary: str,
        evidence: list[str],
        replicas: int | None,
    ) -> Incident:
        """O Hermes concluiu, numa conversa, que algo precisa de correção. Vira um card + pedido de aprovação."""
        pod = await asyncio.to_thread(k8s.first_pod_of, namespace, deployment) or deployment
        inc = Incident(
            id=_new_id(),
            type="HermesProposal",
            namespace=namespace,
            pod=pod,
            container=deployment,
            deployment=deployment,
            reason="proposta do Hermes",
            logs="",
            events="",
            simulated=False,
        )
        rca = {
            "rootCause": root_cause,
            "evidence": evidence,
            "confidence": "média",
            "source": "hermes-chat+mcp",
            "recommendedAction": {"type": action, "replicas": replicas, "reason": root_cause},
            "stakeholderSummary": summary,
            "followUps": [],
            "runbooks": [],
        }
        inc.rca = rca
        inc.proposedBy = "hermes"
        await self._register(inc)
        await self._set_status(inc, "investigating")
        await self._mark(inc, f"Hermes propôs pelo chat: {action} em {namespace}/{deployment} — {root_cause}")
        self._spawn(self._hermes_proposal_scene(inc, rca))
        return inc

    async def _hermes_proposal_scene(self, inc: Incident, rca: dict) -> None:
        await investigator.emit(
            "talking",
            f"Hermes: {rca['rootCause']}",
            incident_id=inc.id,
            log="\n".join(rca.get("evidence", [])[:4]),
            kanban=KanbanAction(
                op="create",
                cardId=inc.id,
                agentId="investigator",
                progress=50,
                title=f"Hermes: {inc.namespace}/{inc.deployment}",
                column="Investigando",
            ),
        )
        await asyncio.sleep(STEP)
        if rca.get("stakeholderSummary"):
            await supervisor.emit("talking", rca["stakeholderSummary"], incident_id=inc.id)
            await asyncio.sleep(STEP)
        await investigator.go_home()
        await self._request_approval(inc, rca)

    # ------------------------------------------------------------------ aprovação humana
    async def _learn(self, inc: Incident, decision: str, reason: str) -> None:
        if not reason.strip():
            return
        try:
            path = await asyncio.to_thread(brain.write_lesson, inc, decision, reason)
            if path:
                await self._mark(inc, f"Lição registrada no Hermes Brain: {path.stem}")
                await itsm.emit(
                    "writing",
                    "Anotei a sua decisão como lição para o time.",
                    incident_id=inc.id,
                    log=f"lição: {path.stem}",
                )
        except Exception as exc:
            log.warning("falha gravando lição: %s", exc)

    def _decide(self, inc: Incident, decision: str, actor: str, reason: str) -> None:
        if actor != "sistema" and inc.proposedBy == actor:
            raise PermissionError("quem propôs a correção não pode decidir sobre ela (separação de deveres)")
        inc.decision = decision  # type: ignore[assignment]
        inc.decisionBy, inc.decisionReason, inc.decidedAt = actor, (reason.strip() or None), now_iso()

    async def acknowledge(self, incident_id: str, actor: str) -> Incident:
        """Alguém assumiu o incidente (conta para o MTTA e para o SLA de reconhecimento)."""
        inc = self.incidents.get(incident_id)
        if not inc or inc.status not in OPEN:
            raise KeyError(incident_id)
        if not inc.acknowledgedAt:
            inc.acknowledgedAt, inc.acknowledgedBy = now_iso(), actor
            await self._mark(inc, f"{actor} reconheceu o incidente", actor=actor, kind="ack")
        if inc.status == "detected":
            await self._set_status(inc, "acknowledged", actor)
        else:
            await self._save(inc)
        return inc

    async def approve(self, incident_id: str, reason: str = "", actor: str = "operador") -> Incident:
        inc = self.incidents.get(incident_id)
        if not inc or inc.status != "waiting_approval" or not inc.approval:
            raise KeyError(incident_id)
        self._decide(inc, "approved", actor, reason)
        await self._mark(inc, f"{actor} aprovou: {inc.approval.command}", actor=actor, kind="decision")
        await self._set_status(inc, "remediating", actor)
        self._spawn(self._learn(inc, "approved", reason))
        await bus.publish({"type": "approval_resolved", "incidentId": inc.id, "decision": "approved"})
        self._spawn(self._execute(inc))
        return inc

    async def reject(self, incident_id: str, reason: str = "", actor: str = "operador") -> Incident:
        inc = self.incidents.get(incident_id)
        if not inc or inc.status != "waiting_approval":
            raise KeyError(incident_id)
        self._decide(inc, "rejected", actor, reason)
        inc.remediationResult = f"rejeitada por {actor}"
        await self._mark(
            inc,
            f"{actor} rejeitou a remediação" + (f": {reason.strip()}" if reason.strip() else ""),
            actor=actor,
            kind="decision",
        )
        await self._set_status(inc, "closed", actor)
        self._spawn(self._learn(inc, "rejected", reason))
        await bus.publish({"type": "approval_resolved", "incidentId": inc.id, "decision": "rejected"})
        await executor.go_home("idle", "Entendido, nada foi alterado no cluster.")
        self._spawn(self._close(inc))
        return inc

    async def _execute(self, inc: Incident) -> None:
        if inc.approval is None:  # nunca deveria acontecer: approve() exige um pedido pendente
            raise RuntimeError(f"{inc.id} sem pedido de aprovação")
        a = inc.approval
        await executor.emit(
            "executing",
            "Aprovado! Aplicando a correção…",
            incident_id=inc.id,
            log=a.command,
            kanban=KanbanAction(op="move", cardId=inc.id, column="Corrigindo", agentId="executor", progress=80),
        )
        await asyncio.sleep(STEP)
        try:
            if a.action == "none":
                result = "nenhuma ação automática; seguir o runbook manualmente"
            elif inc.simulated:
                result = f"[simulação] {a.command}: OK (cluster real não foi alterado)"
            else:
                ns, name = inc.namespace, inc.deployment or inc.pod
                if a.action == "rollout_restart":
                    result = await asyncio.to_thread(k8s.rollout_restart, ns, name)
                elif a.action == "scale":
                    replicas = int((inc.rca or {}).get("recommendedAction", {}).get("replicas") or 2)
                    result = await asyncio.to_thread(k8s.scale, ns, name, replicas)
                else:
                    result = await asyncio.to_thread(k8s.delete_pod, ns, inc.pod)
            inc.remediationResult = result
            await self._set_status(inc, "resolved")
            await self._mark(inc, f"Executor: {result}")
            await executor.emit("done", "Correção aplicada com sucesso.", incident_id=inc.id, log=result)
        except (K8sUnavailable, Exception) as exc:
            inc.remediationResult = f"falhou: {exc}"
            await self._set_status(inc, "failed")
            await self._mark(inc, f"Executor falhou: {exc}")
            await executor.emit(
                "error", "Não consegui aplicar. Precisa de um humano.", incident_id=inc.id, log=str(exc)[:500]
            )
        await asyncio.sleep(STEP)
        await executor.go_home()
        await self._close(inc)

    # ------------------------------------------------------------------ ITSM fecha o ciclo
    async def _close(self, inc: Incident) -> None:
        await itsm.walk("VAULT", "Escrevendo o post-mortem…", incident_id=inc.id)
        await asyncio.sleep(STEP)
        await itsm.emit("writing", "Registrando o aprendizado no Hermes Brain.", zone="VAULT", incident_id=inc.id)
        try:
            path = await asyncio.to_thread(obsidian.write_postmortem, inc, self.timelines.get(inc.id, []))
            inc.postmortemPath = str(path)
            note = f"Hermes Brain: {path.stem} (+ serviço e padrão atualizados)"
            if inc.status == "resolved":
                await self._set_status(inc, "postmortem")
        except Exception as exc:
            note = f"post-mortem falhou: {exc}"
        if github_configured():
            try:
                inc.issueUrl = await asyncio.to_thread(create_issue, inc)
                note += f" | issue: {inc.issueUrl}"
            except Exception as exc:
                note += f" | GitHub falhou: {type(exc).__name__}"
        await asyncio.sleep(STEP / 2)
        await self._save(inc)
        final = {
            "resolved": "Incidente resolvido e documentado.",
            "postmortem": "Incidente resolvido e documentado.",
            "closed": "Incidente encerrado sem alteração.",
            "failed": "Falha registrada; aguardando ação humana.",
        }.get(inc.status, "Incidente documentado.")
        await itsm.emit(
            "done",
            final,
            zone="KANBAN_WALL",
            incident_id=inc.id,
            log=note,
            kanban=KanbanAction(
                op="move", cardId=inc.id, column="Concluído", agentId="itsm", progress=100, url=inc.issueUrl
            ),
        )
        await supervisor.emit("talking", final, incident_id=inc.id)
        await asyncio.sleep(STEP)
        await itsm.go_home()
        await supervisor.go_home()

    # ------------------------------------------------------------------ subida: retomar o que ficou aberto
    async def recover(self) -> int:
        """Carrega do banco os incidentes abertos. Pedidos de aprovação sobrevivem a reinícios;
        investigações interrompidas recomeçam; correções interrompidas viram falha para um humano conferir."""
        try:
            items = await repo.open_incidents()
        except Exception as exc:
            log.warning("não consegui carregar incidentes abertos: %s", type(exc).__name__)
            return 0
        for inc in items:
            self.incidents[inc.id] = inc
            if inc.status in ("detected", "acknowledged", "investigating"):
                await self._mark(inc, "backend reiniciado: retomando a investigação")
                self._spawn(self.run_incident(inc, use_ai=not inc.simulated))
            elif inc.status in ("remediating", "monitoring"):
                await self._mark(inc, "backend reiniciado durante a correção: confira o estado manualmente")
                await self._set_status(inc, "failed")
        if items:
            log.info("%d incidente(s) aberto(s) retomado(s) do banco", len(items))
        return len(items)

    # ------------------------------------------------------------------ teste de comunicação (0 IA)
    async def test_communication(self) -> None:
        if self._comm_lock.locked():
            return
        async with self._comm_lock:
            await supervisor.walk("AGENT_FACTORY", "Monitor, tudo certo por aí?")
            await asyncio.sleep(STEP)
            k = await asyncio.to_thread(k8s.check)
            msg = (
                f"Cluster ok: {k.get('nodes', 0)} nó(s) no ar."
                if k["ok"]
                else "Sem cluster local. Modo simulação ativo."
            )
            await monitor.emit("talking", msg, log=k.get("detail", ""))
            await asyncio.sleep(STEP)
            h = await hermes.ping()
            hm = (
                f"Hermes no VPS respondeu em {h.get('latencyMs', '?')} ms."
                if h["ok"]
                else f"Hermes indisponível: {h.get('detail')}"
            )
            await supervisor.emit("talking", hm, zone="AGENT_FACTORY", log=str(h))
            await asyncio.sleep(STEP)
            await monitor.emit("monitoring", "Combinado. Sigo vigiando.")
            await supervisor.go_home("idle", "Comunicação ok entre os agentes.")


orchestrator = Orchestrator()
