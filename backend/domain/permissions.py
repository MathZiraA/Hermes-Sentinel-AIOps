"""Papéis, permissões e escopo (puro, sem I/O)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["admin", "operator", "viewer", "auditor"]
ROLES: tuple[Role, ...] = ("admin", "operator", "viewer", "auditor")

ROLE_LABEL = {"admin": "Administrador", "operator": "Operador", "viewer": "Visualizador", "auditor": "Auditor"}

READ = frozenset({"incidents:read", "reports:read", "clusters:read", "brain:read", "health:read"})
PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": READ,
    "auditor": READ | {"audit:read"},
    "operator": READ | {"incidents:ack", "incidents:decide", "incidents:simulate", "brain:write"},
    "admin": READ
    | {
        "incidents:ack",
        "incidents:decide",
        "incidents:simulate",
        "brain:write",
        "audit:read",
        "users:manage",
        "teams:manage",
        "settings:manage",
    },
}


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, frozenset())


@dataclass(frozen=True)
class Scope:
    cluster: str = "*"
    namespace: str = "*"

    def allows(self, cluster: str, namespace: str) -> bool:
        return self.cluster in ("*", cluster) and self.namespace in ("*", namespace)


@dataclass(frozen=True)
class Principal:
    """Quem está fazendo a requisição, já com o escopo resolvido."""

    id: str
    email: str
    name: str
    role: str
    scopes: tuple[Scope, ...] = field(default_factory=tuple)
    mfa: bool = False

    @property
    def unrestricted(self) -> bool:
        """Admin e Auditor enxergam todos os clusters; os outros papéis só o escopo dos seus times."""
        return self.role in ("admin", "auditor") or any(s.cluster == "*" and s.namespace == "*" for s in self.scopes)

    def can(self, permission: str) -> bool:
        return has_permission(self.role, permission)

    def sees(self, cluster: str, namespace: str) -> bool:
        return self.unrestricted or any(s.allows(cluster, namespace) for s in self.scopes)


def merge_scopes(rows: Iterable[tuple[str, str]]) -> tuple[Scope, ...]:
    return tuple(sorted({Scope(c or "*", n or "*") for c, n in rows}, key=lambda s: (s.cluster, s.namespace)))
