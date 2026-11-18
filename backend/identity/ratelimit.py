"""Bloqueio contra força bruta no login: 5 falhas em 15 min bloqueiam por 15 min (por IP e por e-mail)."""

from __future__ import annotations

import time

MAX_FAILURES = 5
WINDOW = 15 * 60

_failures: dict[str, list[float]] = {}


def _keys(ip: str | None, email: str) -> list[str]:
    return [f"email:{email.lower()}", f"ip:{ip or '-'}"]


def _recent(key: str, now: float) -> list[float]:
    hits = [t for t in _failures.get(key, []) if now - t < WINDOW]
    _failures[key] = hits
    return hits


def is_locked(ip: str | None, email: str) -> bool:
    now = time.monotonic()
    return any(len(_recent(k, now)) >= MAX_FAILURES for k in _keys(ip, email))


def record_failure(ip: str | None, email: str) -> None:
    now = time.monotonic()
    for k in _keys(ip, email):
        _recent(k, now).append(now)


def reset(ip: str | None, email: str) -> None:
    for k in _keys(ip, email):
        _failures.pop(k, None)


def clear_all() -> None:
    _failures.clear()
