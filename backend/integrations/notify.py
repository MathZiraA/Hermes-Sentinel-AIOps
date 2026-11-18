"""Notificações de incidente. Os canais se registram aqui (o Jira entra na Fase 5).

Um canal com erro nunca derruba o fluxo do incidente.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger("sentinel.notify")

# kind: opened | escalated | waiting_approval | auto_remediated | resolved | closed | failed | reopened
Channel = Callable[[str, Any, str], Awaitable[None]]
_channels: list[tuple[str, Channel]] = []


def register(name: str, channel: Channel) -> None:
    _channels.append((name, channel))


def channels() -> list[str]:
    return [n for n, _ in _channels]


async def notify(kind: str, incident: Any, text: str) -> None:
    for name, channel in _channels:
        try:
            await channel(kind, incident, text)
        except Exception as exc:
            log.warning("canal %s falhou (%s): %s", name, kind, type(exc).__name__)
