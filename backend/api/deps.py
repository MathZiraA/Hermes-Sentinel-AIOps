"""Dependências comuns das rotas: quem está chamando e de onde."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class Actor:
    """Quem faz a ação. Até o login (Fase 2) existir, toda ação humana é do "operador" local."""

    name: str
    ip: str | None


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def current_actor(request: Request) -> Actor:
    return Actor(name="operador", ip=client_ip(request))
