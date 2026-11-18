"""Login, sessão, troca de senha, 2FA e SSO (OIDC)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from api.deps import COOKIE, client_ip, current_principal
from config import settings
from db import repository as repo
from domain.permissions import PERMISSIONS, ROLE_LABEL, Principal
from identity import oidc, service
from identity.crypto import WeakPassword

router = APIRouter(prefix="/api/auth", tags=["autenticação"])
OIDC_COOKIE = "sentinel_oidc"


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    code: str | None = Field(default=None, max_length=10)


class PasswordChange(BaseModel):
    current: str = Field(max_length=256)
    new: str = Field(min_length=1, max_length=256)


class Code(BaseModel):
    code: str = Field(max_length=10)


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def me_payload(p: Principal) -> dict[str, Any]:
    return {
        "id": p.id,
        "email": p.email,
        "name": p.name,
        "role": p.role,
        "roleLabel": ROLE_LABEL.get(p.role, p.role),
        "permissions": sorted(PERMISSIONS.get(p.role, frozenset())),
        "scopes": [{"cluster": s.cluster, "namespace": s.namespace} for s in p.scopes],
        "unrestricted": p.unrestricted,
        "mfa": p.mfa,
    }


@router.get("/config", summary="Como fazer login nesta instalação (público)")
async def auth_config() -> dict[str, Any]:
    return {
        "authEnabled": settings.auth_enabled,
        "oidc": oidc.enabled(),
        "needsSetup": await service.count_users() == 0,
    }


@router.post("/login", summary="Entrar com e-mail, senha e, se ativo, código 2FA")
async def login(body: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    ip = client_ip(request)
    try:
        user = await service.authenticate(body.email, body.password, body.code, ip)
    except service.AuthError as exc:
        if exc.code != "mfa_required":
            await repo.audit(body.email.strip().lower()[:120], "auth.login_failed", "", {"reason": exc.code}, ip)
        status = {"mfa_required": 401, "locked": 429, "inactive": 403}.get(exc.code, 401)
        raise HTTPException(status, {"code": exc.code, "message": str(exc)}) from exc
    token = await service.create_session(user, ip, request.headers.get("user-agent"))
    _set_cookie(response, token)
    await repo.audit(user.email, "auth.login", "", {"method": "senha", "mfa": bool(body.code)}, ip)
    return me_payload(await service.principal_for(user))


@router.post("/logout", summary="Sair (revoga a sessão)")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(COOKIE)
    principal = await service.resolve_session(token)
    await service.revoke_session(token)
    response.delete_cookie(COOKIE, path="/")
    if principal:
        await repo.audit(principal.email, "auth.logout", "", {}, client_ip(request))
    return {"ok": True}


@router.get("/me", summary="Usuário logado, papel, permissões e escopo")
async def me(principal: Annotated[Principal, Depends(current_principal)]) -> dict[str, Any]:
    return me_payload(principal)


@router.post("/password", summary="Trocar a própria senha")
async def change_password(
    body: PasswordChange, request: Request, principal: Annotated[Principal, Depends(current_principal)]
) -> dict[str, bool]:
    try:
        await service.set_password(principal.id, body.new, current_password=body.current)
    except WeakPassword as exc:
        raise HTTPException(422, str(exc)) from exc
    except service.AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    await repo.audit(principal.email, "auth.password_changed", principal.email, {}, client_ip(request))
    return {"ok": True}


@router.post("/totp/setup", summary="Começar a configurar o 2FA (devolve o segredo e o QR otpauth://)")
async def totp_setup(principal: Annotated[Principal, Depends(current_principal)]) -> dict[str, str]:
    try:
        return await service.totp_begin(principal.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/totp/enable", summary="Confirmar o 2FA com um código do aplicativo")
async def totp_enable(
    body: Code, request: Request, principal: Annotated[Principal, Depends(current_principal)]
) -> dict[str, bool]:
    try:
        await service.totp_confirm(principal.id, body.code)
    except (ValueError, service.AuthError) as exc:
        raise HTTPException(400, str(exc)) from exc
    await repo.audit(principal.email, "auth.mfa_enabled", principal.email, {}, client_ip(request))
    return {"ok": True}


@router.post("/totp/disable", summary="Desligar o 2FA (exige um código válido)")
async def totp_disable(
    body: Code, request: Request, principal: Annotated[Principal, Depends(current_principal)]
) -> dict[str, bool]:
    try:
        await service.totp_disable(principal.id, body.code)
    except (ValueError, service.AuthError) as exc:
        raise HTTPException(400, str(exc)) from exc
    await repo.audit(principal.email, "auth.mfa_disabled", principal.email, {}, client_ip(request))
    return {"ok": True}


# --------------------------------------------------------------------------- SSO
@router.get("/oidc/login", summary="Começar o login pelo provedor SSO")
async def oidc_login() -> RedirectResponse:
    if not oidc.enabled():
        raise HTTPException(404, "SSO não configurado")
    url, cookie = await oidc.authorization_url()
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(
        OIDC_COOKIE,
        cookie,
        max_age=oidc.STATE_TTL,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/auth/oidc",
    )
    return resp


@router.get("/oidc/callback", summary="Retorno do provedor SSO")
async def oidc_callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    ip = client_ip(request)
    try:
        claims = await oidc.complete(code, state, request.cookies.get(OIDC_COOKIE))
        user = await service.find_or_create_sso_user(claims["sub"], claims["email"], claims["name"])
    except (oidc.OidcError, service.AuthError) as exc:
        await repo.audit("sso", "auth.login_failed", "", {"reason": str(exc)[:200]}, ip)
        return RedirectResponse(f"{settings.frontend_url}/login?erro=sso", status_code=302)
    token = await service.create_session(user, ip, request.headers.get("user-agent"))
    resp = RedirectResponse(f"{settings.frontend_url}/", status_code=302)
    _set_cookie(resp, token)
    resp.delete_cookie(OIDC_COOKIE, path="/api/auth/oidc")
    await repo.audit(user.email, "auth.login", "", {"method": "sso"}, ip)
    return resp


# --------------------------------------------------------------------------- primeira configuração
class SetupRequest(BaseModel):
    email: str = Field(max_length=254)
    name: str = Field(max_length=120)
    password: str = Field(max_length=256)


@router.post("/setup", summary="Criar o primeiro administrador (só funciona com o banco sem usuários)")
async def first_admin(body: SetupRequest, request: Request, response: Response) -> dict[str, Any]:
    if await service.count_users() > 0:
        raise HTTPException(409, "a instalação já foi configurada")
    try:
        user = await service.create_user(body.email, body.name, "admin", body.password)
    except (ValueError, WeakPassword) as exc:
        raise HTTPException(422, str(exc)) from exc
    ip = client_ip(request)
    token = await service.create_session(user, ip, request.headers.get("user-agent"))
    _set_cookie(response, token)
    await repo.audit(user.email, "auth.setup_admin", user.email, {}, ip)
    return me_payload(await service.principal_for(user))
