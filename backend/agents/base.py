"""Agente da cena: identidade fixa + helper para emitir eventos padronizados."""

from __future__ import annotations

from core.bus import AGENT_HOME, bus
from schemas.events import AgentEvent, ApprovalRequest, KanbanAction


class SentinelAgent:
    def __init__(self, agent_id: str) -> None:
        meta = AGENT_HOME[agent_id]
        self.id = agent_id
        self.name = meta["name"]
        self.role = meta["role"]
        self.home = meta["zone"]

    async def emit(
        self,
        status: str,
        bubble: str = "",
        *,
        zone: str | None = None,
        log: str = "",
        incident_id: str | None = None,
        kanban: KanbanAction | None = None,
        approval: ApprovalRequest | None = None,
    ) -> None:
        await bus.emit(
            AgentEvent(
                agentId=self.id,  # type: ignore[arg-type]
                agentName=self.name,
                role=self.role,
                status=status,  # type: ignore[arg-type]
                targetZone=(zone or self.home),  # type: ignore[arg-type]
                bubbleMessage=bubble,
                technicalLog=log,
                incidentId=incident_id,
                kanbanAction=kanban,
                approvalRequest=approval,
            )
        )

    async def walk(self, zone: str, bubble: str = "", **kw: object) -> None:
        await self.emit("walking", bubble, zone=zone, **kw)  # type: ignore[arg-type]

    async def go_home(self, status: str = "idle", bubble: str = "") -> None:
        await self.emit(status, bubble, zone=self.home)


monitor = SentinelAgent("monitor")
supervisor = SentinelAgent("supervisor")
investigator = SentinelAgent("investigator")
executor = SentinelAgent("executor")
itsm = SentinelAgent("itsm")
