"""Administração de usuários e times (papel Admin)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.deps import client_ip, require
from db import repository as repo
from domain.permissions import Principal
from identity import service
from identity.crypto import WeakPassword

router = APIRouter(prefix="/api/admin", tags=["administração"])
UsersAdmin = Annotated[Principal, Depends(require("users:manage"))]
TeamsAdmin = Annotated[Principal, Depends(require("teams:manage"))]


class NewUser(BaseModel):
    email: str = Field(max_length=254)
    name: str = Field(max_length=120)
    role: str
    password: str | None = Field(default=None, max_length=256)


class UserPatch(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    role: str | None = None
    active: bool | None = None


class PasswordReset(BaseModel):
    password: str = Field(max_length=256)


class ScopeIn(BaseModel):
    cluster: str = Field(default="*", max_length=63)
    namespace: str = Field(default="*", max_length=63)


class TeamIn(BaseModel):
    name: str = Field(max_length=120)


class TeamUpdate(BaseModel):
    members: list[str] = Field(default_factory=list)
    scopes: list[ScopeIn] = Field(default_factory=list)


@router.get("/users")
async def list_users(_: UsersAdmin) -> list[dict[str, Any]]:
    return await service.list_users()


@router.post("/users", status_code=201)
async def create_user(body: NewUser, request: Request, admin: UsersAdmin) -> dict[str, Any]:
    try:
        user = await service.create_user(body.email, body.name, body.role, body.password)
    except (ValueError, WeakPassword) as exc:
        raise HTTPException(422, str(exc)) from exc
    await repo.audit(admin.email, "user.create", user.email, {"role": user.role}, client_ip(request))
    return service.user_dict(user)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UserPatch, request: Request, admin: UsersAdmin) -> dict[str, Any]:
    if user_id == admin.id and (body.active is False or (body.role and body.role != "admin")):
        raise HTTPException(422, "você não pode rebaixar nem desativar a si mesmo")
    try:
        user = await service.update_user(user_id, name=body.name, role=body.role, active=body.active)
    except service.NotFound as exc:
        raise HTTPException(404, "usuário não encontrado") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await repo.audit(admin.email, "user.update", user.email, body.model_dump(exclude_none=True), client_ip(request))
    return service.user_dict(user)


@router.post("/users/{user_id}/password")
async def reset_password(user_id: str, body: PasswordReset, request: Request, admin: UsersAdmin) -> dict[str, bool]:
    try:
        await service.set_password(user_id, body.password)
        user = await service.get_user(user_id)
    except service.NotFound as exc:
        raise HTTPException(404, "usuário não encontrado") from exc
    except WeakPassword as exc:
        raise HTTPException(422, str(exc)) from exc
    await repo.audit(admin.email, "user.password_reset", user.email, {}, client_ip(request))
    return {"ok": True}


@router.get("/teams")
async def list_teams(_: TeamsAdmin) -> list[dict[str, Any]]:
    return await service.list_teams()


@router.post("/teams", status_code=201)
async def create_team(body: TeamIn, request: Request, admin: TeamsAdmin) -> dict[str, Any]:
    try:
        team = await service.create_team(body.name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await repo.audit(admin.email, "team.create", team["name"], {}, client_ip(request))
    return team


@router.put("/teams/{team_id}")
async def update_team(team_id: str, body: TeamUpdate, request: Request, admin: TeamsAdmin) -> dict[str, bool]:
    try:
        await service.set_team(team_id, body.members, [s.model_dump() for s in body.scopes])
    except service.NotFound as exc:
        raise HTTPException(404, "time não encontrado") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await repo.audit(admin.email, "team.update", team_id, body.model_dump(), client_ip(request))
    return {"ok": True}


@router.delete("/teams/{team_id}")
async def delete_team(team_id: str, request: Request, admin: TeamsAdmin) -> dict[str, bool]:
    try:
        await service.delete_team(team_id)
    except service.NotFound as exc:
        raise HTTPException(404, "time não encontrado") from exc
    await repo.audit(admin.email, "team.delete", team_id, {}, client_ip(request))
    return {"ok": True}
