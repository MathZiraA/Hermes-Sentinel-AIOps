"""Barramento de telemetria: guarda o estado da cena e transmite eventos para os WebSockets."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from typing import Any

from fastapi import WebSocket

from schemas.events import AgentEvent, KanbanAction, now_iso

log = logging.getLogger("sentinel.bus")

# Posição "de casa" e papel de cada agente na cena isométrica.
AGENT_HOME: dict[str, dict[str, str]] = {
    "monitor": {"name": "Monitor", "role": "Watcher do cluster", "zone": "AGENT_FACTORY"},
    "supervisor": {"name": "Supervisor", "role": "Coordenador", "zone": "CENTRAL_HUB"},
    "investigator": {"name": "Investigator", "role": "Análise de causa raiz", "zone": "WHITEBOARD"},
    "executor": {"name": "Executor", "role": "Remediação", "zone": "WORKSTATION"},
    "itsm": {"name": "ITSM", "role": "Kanban, Issues e Post-Mortem", "zone": "VAULT"},
}


class TelemetryBus:
    def __init__(self, history: int = 200) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.events: deque[dict[str, Any]] = deque(maxlen=history)
        self.agents: dict[str, dict[str, Any]] = {
            aid: {
                "agentId": aid,
                "agentName": meta["name"],
                "role": meta["role"],
                "status": "monitoring" if aid == "monitor" else "idle",
                "zone": meta["zone"],
                "bubbleMessage": "",
                "updatedAt": now_iso(),
            }
            for aid, meta in AGENT_HOME.items()
        }
        self.kanban: dict[str, dict[str, Any]] = {}
        self.health: dict[str, Any] = {}

    # ------------------------------------------------------------------ clients
    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        await ws.send_text(json.dumps(self.snapshot()))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def snapshot(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "timestamp": now_iso(),
            "agents": list(self.agents.values()),
            "kanban": list(self.kanban.values()),
            "health": self.health,
            "events": list(self.events)[-40:],
        }

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        text = json.dumps(payload, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_text(text)
            except Exception:  # cliente caiu no meio do envio
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    # ------------------------------------------------------------------ publish
    async def emit(self, event: AgentEvent) -> dict[str, Any]:
        data = event.model_dump(mode="json")
        agent = self.agents[event.agentId]
        agent.update(
            status=event.status,
            zone=event.targetZone,
            bubbleMessage=event.bubbleMessage,
            updatedAt=event.timestamp,
        )
        if event.kanbanAction:
            self._apply_kanban(event.kanbanAction)
        self.events.append(data)
        log.info("[%s] %s → %s | %s", event.agentId, event.status, event.targetZone, event.bubbleMessage)
        await self._broadcast(data)
        return data

    async def publish_health(self, health: dict[str, Any]) -> None:
        self.health = health
        await self._broadcast({"type": "health", "timestamp": now_iso(), "health": health})

    async def publish(self, payload: dict[str, Any]) -> None:
        """Mensagens livres (ex.: approval_resolved)."""
        payload.setdefault("timestamp", now_iso())
        await self._broadcast(payload)

    def _apply_kanban(self, action: KanbanAction) -> None:
        card = self.kanban.setdefault(
            action.cardId,
            {"cardId": action.cardId, "title": action.title or action.cardId, "column": "Backlog", "progress": 0},
        )
        for key in ("title", "column", "agentId", "progress", "url"):
            value = getattr(action, key)
            if value is not None:
                card[key] = value
        card["updatedAt"] = now_iso()


bus = TelemetryBus()
