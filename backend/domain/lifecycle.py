"""Regras de negócio do incidente: ciclo de vida, severidade (SEV1–SEV4) e SLA.

Puro (sem I/O): fácil de testar e de reaproveitar na API, no orquestrador e nos relatórios.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

Status = Literal[
    "detected",
    "acknowledged",
    "investigating",
    "waiting_approval",
    "remediating",
    "monitoring",
    "resolved",
    "postmortem",
    "closed",
    "failed",
]
Sev = Literal["SEV1", "SEV2", "SEV3", "SEV4"]

STATUS_LABEL: dict[str, str] = {
    "detected": "Detectado",
    "acknowledged": "Reconhecido",
    "investigating": "Investigando",
    "waiting_approval": "Aguardando aprovação",
    "remediating": "Corrigindo",
    "monitoring": "Monitorando",
    "resolved": "Resolvido",
    "postmortem": "Post-mortem",
    "closed": "Encerrado sem alteração",
    "failed": "Falhou (ação humana)",
}

# Estados em que o incidente ainda exige atenção
OPEN: frozenset[str] = frozenset(
    {"detected", "acknowledged", "investigating", "waiting_approval", "remediating", "monitoring"}
)
TERMINAL: frozenset[str] = frozenset({"resolved", "postmortem", "closed", "failed"})

# Transições válidas. Reabrir (monitoring/resolved/failed → investigating) é permitido de propósito:
# a verificação pós-correção reabre o incidente se o problema voltar.
TRANSITIONS: dict[str, frozenset[str]] = {
    "detected": frozenset({"acknowledged", "investigating", "closed"}),
    "acknowledged": frozenset({"investigating", "closed"}),
    "investigating": frozenset({"acknowledged", "waiting_approval", "closed", "failed"}),
    "waiting_approval": frozenset({"remediating", "closed"}),
    "remediating": frozenset({"monitoring", "resolved", "failed"}),
    "monitoring": frozenset({"resolved", "investigating", "failed"}),
    "resolved": frozenset({"postmortem", "investigating"}),
    "postmortem": frozenset(),
    "closed": frozenset({"investigating"}),
    "failed": frozenset({"investigating", "closed"}),
}

# Nomes antigos (0.1.0) → ciclo novo, para ler dados já gravados
LEGACY_STATUS = {"open": "detected", "rejected": "closed"}


class InvalidTransition(ValueError):
    pass


def normalize_status(status: str) -> str:
    return LEGACY_STATUS.get(status, status)


def can_transition(current: str, new: str) -> bool:
    return new in TRANSITIONS.get(normalize_status(current), frozenset())


def check_transition(current: str, new: str) -> None:
    if current == new:
        return
    if not can_transition(current, new):
        raise InvalidTransition(f"transição inválida: {current} → {new}")


# --------------------------------------------------------------------------- severidade
SEV_BY_TYPE: dict[str, Sev] = {
    # SEV1: serviço ou infraestrutura fora do ar
    "NodeNotReady": "SEV1",
    "DeploymentDown": "SEV1",
    "PVCLost": "SEV1",
    # SEV2: workload falhando
    "OOMKilled": "SEV2",
    "CrashLoopBackOff": "SEV2",
    "ImagePullBackOff": "SEV2",
    "CreateContainerConfigError": "SEV2",
    "CreateContainerError": "SEV2",
    "RunContainerError": "SEV2",
    "InvalidImageName": "SEV2",
    "ProgressDeadlineExceeded": "SEV2",
    "StatefulSetDegraded": "SEV2",
    "NodeMemoryPressure": "SEV2",
    "NodeDiskPressure": "SEV2",
    "NodePIDPressure": "SEV2",
    "Evicted": "SEV2",
    "PodFailed": "SEV2",
    # SEV3: degradação ou falha isolada
    "FailedScheduling": "SEV3",
    "NotReady": "SEV3",
    "JobFailed": "SEV3",
    "PVCPending": "SEV3",
    "HermesProposal": "SEV3",
    # SEV4: aviso antecipado
    "HPAMaxedOut": "SEV4",
    "MemoryNearLimit": "SEV4",
}
SEV_BY_DETECTION = {"crítica": "SEV1", "alta": "SEV2", "média": "SEV3", "baixa": "SEV4"}


def severity_for(incident_type: str, detection_severity: str | None = None) -> Sev:
    """Tipo conhecido manda; senão, a severidade sugerida pelo Monitor; senão SEV3."""
    if incident_type in SEV_BY_TYPE:
        return SEV_BY_TYPE[incident_type]
    return SEV_BY_DETECTION.get(detection_severity or "", "SEV3")  # type: ignore[return-value]


# --------------------------------------------------------------------------- SLA
def _parse_minutes(raw: str, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    try:
        vals = tuple(int(x) for x in raw.split(","))
        if len(vals) == 4 and all(v > 0 for v in vals):
            return vals  # type: ignore[return-value]
    except ValueError:
        pass
    return default


DEFAULT_ACK = (5, 15, 60, 1440)  # minutos para reconhecer: SEV1..SEV4
DEFAULT_RESOLVE = (60, 240, 1440, 4320)  # minutos para resolver


class SlaPolicy:
    def __init__(self, ack: str = "", resolve: str = "") -> None:
        self.ack = _parse_minutes(ack, DEFAULT_ACK)
        self.resolve = _parse_minutes(resolve, DEFAULT_RESOLVE)

    @staticmethod
    def _idx(sev: str) -> int:
        return max(0, min(3, int(sev[-1]) - 1)) if sev.startswith("SEV") else 2

    def ack_due(self, sev: str, detected: datetime) -> datetime:
        return detected + timedelta(minutes=self.ack[self._idx(sev)])

    def resolve_due(self, sev: str, detected: datetime) -> datetime:
        return detected + timedelta(minutes=self.resolve[self._idx(sev)])

    def evaluate(
        self,
        sev: str,
        detected: datetime,
        acknowledged: datetime | None,
        resolved: datetime | None,
        now: datetime,
    ) -> dict[str, object]:
        """Estado do SLA: prazos e se foram (ou estão sendo) estourados."""
        ack_due, res_due = self.ack_due(sev, detected), self.resolve_due(sev, detected)
        return {
            "ackDueAt": ack_due.isoformat(),
            "resolveDueAt": res_due.isoformat(),
            "ackBreached": (acknowledged or now) > ack_due,
            "resolveBreached": (resolved or now) > res_due,
        }
