"""Contratos JSON trocados entre backend e frontend (WebSocket /ws/telemetry e REST)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from domain.lifecycle import Sev, Status, normalize_status

AgentId = Literal["monitor", "supervisor", "investigator", "executor", "itsm"]
Zone = Literal["AGENT_FACTORY", "CENTRAL_HUB", "WHITEBOARD", "WORKSTATION", "VAULT", "KANBAN_WALL"]
AgentStatus = Literal[
    "idle",
    "monitoring",
    "walking",
    "alert",
    "talking",
    "investigating",
    "thinking",
    "waiting_approval",
    "executing",
    "writing",
    "done",
    "error",
]
IncidentType = Literal["OOMKilled", "CrashLoopBackOff", "ImagePullBackOff"]
KanbanColumn = Literal["Backlog", "Investigando", "Aguardando aprovação", "Corrigindo", "Concluído"]

BUBBLE_MAX = 90


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def clip_bubble(text: str) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= BUBBLE_MAX else text[: BUBBLE_MAX - 1].rstrip() + "…"


class KanbanAction(BaseModel):
    op: Literal["create", "move", "update"]
    cardId: str
    title: str | None = None
    column: KanbanColumn | None = None
    agentId: AgentId | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    url: str | None = None


class ApprovalRequest(BaseModel):
    incidentId: str
    action: str  # ver domain/actions.py
    params: dict = Field(default_factory=dict)  # validados por domain.actions.validate
    command: str
    description: str
    target: str
    risk: Literal["baixo", "médio", "alto"] = "médio"
    simulated: bool = False


class AgentEvent(BaseModel):
    """Evento padronizado de um agente — o frontend anima a cena a partir dele."""

    type: Literal["agent"] = "agent"
    timestamp: str = Field(default_factory=now_iso)
    agentId: AgentId
    agentName: str
    role: str
    status: AgentStatus
    targetZone: Zone
    bubbleMessage: str = ""
    technicalLog: str = ""
    incidentId: str | None = None
    kanbanAction: KanbanAction | None = None
    approvalRequest: ApprovalRequest | None = None

    @field_validator("bubbleMessage")
    @classmethod
    def _clip(cls, v: str) -> str:
        return clip_bubble(v)


class SimulateRequest(BaseModel):
    type: IncidentType = "OOMKilled"
    namespace: str = "stockflow"
    deployment: str = "pedidos"
    # false = RCA demonstrativo local (0 chamadas de IA). true = envia ao Hermes (1 chamada).
    useAi: bool = False


class DecisionRequest(BaseModel):
    """Corpo opcional de aprovar/rejeitar: o motivo vira uma Lição no Hermes Brain."""

    motivo: str = Field(default="", max_length=600)


class Incident(BaseModel):
    id: str
    cluster: str = "local"
    # Qualquer anomalia vira incidente (OOMKilled, FailedMount, NodeDiskPressure…), não só as 3 simuláveis
    type: str
    namespace: str
    pod: str
    container: str | None = None
    deployment: str | None = None
    resourceKind: str = "Pod"
    severity: str = "alta"  # sugestão do Monitor (crítica/alta/média/baixa)
    sev: Sev = "SEV3"
    reason: str
    detectedAt: str = Field(default_factory=now_iso)
    acknowledgedAt: str | None = None
    acknowledgedBy: str | None = None
    resolvedAt: str | None = None
    simulated: bool = False
    status: Status = "detected"
    proposedBy: str = "sistema"  # quem propôs a correção (bot, Hermes ou pessoa)
    decision: Literal["approved", "rejected"] | None = None
    decisionBy: str | None = None
    decisionReason: str | None = None
    decidedAt: str | None = None
    assignedTo: list[str] = Field(default_factory=list)  # plantão responsável agora
    escalationLevel: int = 0  # 0 = ninguém avisado · 1 primário · 2 secundário · 3 administradores
    reopenCount: int = 0  # a verificação pós-correção reabriu o incidente
    rollout: dict | None = None  # deploy recente correlacionado ao incidente
    autoRemediatedBy: str | None = None  # política de autorremediação que aprovou sozinha
    ticket: dict | None = None  # ticket externo (Jira): {"system", "key", "url"}
    rcaRating: dict | None = None  # avaliação humana do diagnóstico: {"correct", "note", "by", "at"}
    source: str = "kubernetes"  # kubernetes | zabbix | hermes
    external: dict | None = None  # dados da origem externa (ex.: evento do Zabbix)
    logs: str = ""
    events: str = ""
    rca: dict | None = None
    memory: str = ""  # o que o Hermes Brain já sabia (vai para o Investigator)
    related: list[str] = Field(default_factory=list)  # sinais correlacionados a este incidente
    approval: ApprovalRequest | None = None
    remediationResult: str | None = None
    postmortemPath: str | None = None
    issueUrl: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _legacy_status(cls, v: str) -> str:
        """Aceita os nomes da 0.1.0 ("open", "rejected") e converte para o ciclo novo."""
        return normalize_status(v) if isinstance(v, str) else v
