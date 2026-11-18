"""Dependências das rotas: quem está chamando, o que pode fazer e de onde."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, WebSocket

from config import settings
from domain.permissions import Principal, Scope
from identity import service

COOKIE = "sentinel_session"

# Com AUTH_ENABLED=false (só para demo local) toda requisição vira este administrador.
LOCAL_ADMIN = Principal(id="local", email="operador", name="Operador local", role="admin", scopes=(Scope(),))


@dataclass(frozen=True)
class Actor:
    """Quem faz a ação, para a auditoria e para a separação de deveres."""

    name: str
    ip: str | None
    principal: Principal


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def optional_principal(request: Request) -> Principal | None:
    if not settings.auth_enabled:
        return LOCAL_ADMIN
    return await service.resolve_session(request.cookies.get(COOKIE))


async def current_principal(principal: Annotated[Principal | None, Depends(optional_principal)]) -> Principal:
    if principal is None:
        raise HTTPException(401, "faça login para continuar")
    return principal


def require(permission: str) -> Callable[..., Awaitable[Principal]]:
    async def checker(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if not principal.can(permission):
            raise HTTPException(403, f"seu papel ({principal.role}) não permite esta ação")
        return principal

    checker.__name__ = f"require_{permission.replace(':', '_')}"
    return checker


def actor_for(permission: str) -> Callable[..., Awaitable[Actor]]:
    checker = require(permission)

    # Depends() como valor padrão (e não em Annotated): com `from __future__ import annotations` a anotação
    # vira texto e o FastAPI não resolveria a variável local `checker`.
    async def dep(request: Request, principal: Principal = Depends(checker)) -> Actor:  # noqa: B008
        return Actor(name=principal.email, ip=client_ip(request), principal=principal)

    return dep


async def current_actor(request: Request, principal: Annotated[Principal, Depends(current_principal)]) -> Actor:
    return Actor(name=principal.email, ip=client_ip(request), principal=principal)


async def websocket_principal(ws: WebSocket) -> Principal | None:
    if not settings.auth_enabled:
        return LOCAL_ADMIN
    return await service.resolve_session(ws.cookies.get(COOKIE))
