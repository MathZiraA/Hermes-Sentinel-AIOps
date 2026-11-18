"""Usuários, times, sessões, 2FA e autenticação."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pyotp
from sqlalchemy import delete, func, select

from config import settings
from db import engine as db
from db.models import SessionRow, Team, TeamMember, TeamScope, User, utcnow
from domain.permissions import ROLES, Principal, merge_scopes
from identity import crypto, ratelimit

log = logging.getLogger("sentinel.identity")
ISSUER = "Hermes Sentinel"
PENDING = "pending:"


class AuthError(Exception):
    """code: invalid | mfa_required | mfa_invalid | inactive | locked"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class NotFound(LookupError):
    pass


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


def _validate_role(role: str) -> str:
    if role not in ROLES:
        raise ValueError(f"papel inválido: {role}. Use um de: {', '.join(ROLES)}")
    return role


def user_dict(u: User, teams: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "active": u.is_active,
        "mfa": bool(u.totp_secret and not u.totp_secret.startswith(PENDING)),
        "sso": bool(u.oidc_subject),
        "teams": teams or [],
        "createdAt": _aware(u.created_at).isoformat() if u.created_at else None,  # type: ignore[union-attr]
        "lastLoginAt": _aware(u.last_login_at).isoformat() if u.last_login_at else None,  # type: ignore[union-attr]
    }


# --------------------------------------------------------------------------- usuários
async def count_users() -> int:
    async with db.session() as s:
        return await s.scalar(select(func.count()).select_from(User)) or 0


async def create_user(email: str, name: str, role: str, password: str | None = None) -> User:
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("e-mail inválido")
    _validate_role(role)
    if password is not None:
        crypto.check_password_policy(password)
    async with db.session() as s:
        if await s.scalar(select(User).where(User.email == email)):
            raise ValueError("já existe um usuário com esse e-mail")
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name.strip() or email,
            role=role,
            password_hash=crypto.hash_password(password) if password else None,
        )
        s.add(user)
        await s.commit()
        return user


async def get_user(user_id: str) -> User:
    async with db.session() as s:
        user = await s.get(User, user_id)
    if not user:
        raise NotFound(user_id)
    return user


async def list_users() -> list[dict[str, Any]]:
    async with db.session() as s:
        users = (await s.scalars(select(User).order_by(User.email))).all()
        memberships = (await s.execute(select(TeamMember.user_id, Team.name).join(Team))).all()
    teams: dict[str, list[str]] = {}
    for uid, tname in memberships:
        teams.setdefault(uid, []).append(tname)
    return [user_dict(u, sorted(teams.get(u.id, []))) for u in users]


async def update_user(
    user_id: str, *, name: str | None = None, role: str | None = None, active: bool | None = None
) -> User:
    async with db.session() as s:
        user = await s.get(User, user_id)
        if not user:
            raise NotFound(user_id)
        if role is not None:
            if user.role == "admin" and role != "admin" and await _admins(s) <= 1:
                raise ValueError("não é possível remover o último administrador")
            user.role = _validate_role(role)
        if active is not None:
            if not active and user.role == "admin" and await _admins(s) <= 1:
                raise ValueError("não é possível desativar o último administrador")
            user.is_active = active
        if name is not None:
            user.name = name.strip() or user.name
        await s.commit()
    if active is False or role is not None:
        await revoke_all(user_id)  # mudança de acesso derruba as sessões abertas
    return user


async def _admins(s: Any) -> int:
    return await s.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active)) or 0


async def set_password(user_id: str, new_password: str, current_password: str | None = None) -> None:
    crypto.check_password_policy(new_password)
    async with db.session() as s:
        user = await s.get(User, user_id)
        if not user:
            raise NotFound(user_id)
        if current_password is not None and not crypto.verify_password(user.password_hash, current_password):
            raise AuthError("invalid", "senha atual incorreta")
        user.password_hash = crypto.hash_password(new_password)
        await s.commit()
    await revoke_all(user_id)


async def bootstrap_admin() -> bool:
    """Primeira subida: cria o admin de SENTINEL_ADMIN_EMAIL/SENTINEL_ADMIN_PASSWORD, se não houver usuários."""
    if await count_users() or not (settings.admin_email and settings.admin_password):
        return False
    await create_user(settings.admin_email, "Administrador", "admin", settings.admin_password)
    log.warning("usuário administrador inicial criado: %s (troque a senha no primeiro acesso)", settings.admin_email)
    return True


# --------------------------------------------------------------------------- times e escopo
async def create_team(name: str) -> dict[str, Any]:
    async with db.session() as s:
        if await s.scalar(select(Team).where(Team.name == name.strip())):
            raise ValueError("já existe um time com esse nome")
        team = Team(id=str(uuid.uuid4()), name=name.strip())
        s.add(team)
        await s.commit()
    return {"id": team.id, "name": team.name, "members": [], "scopes": []}


async def list_teams() -> list[dict[str, Any]]:
    async with db.session() as s:
        teams = (await s.scalars(select(Team).order_by(Team.name))).all()
        members = (await s.execute(select(TeamMember.team_id, User.email).join(User))).all()
        scopes = (await s.scalars(select(TeamScope))).all()
    out = []
    for t in teams:
        out.append(
            {
                "id": t.id,
                "name": t.name,
                "members": sorted(e for tid, e in members if tid == t.id),
                "scopes": [
                    {"cluster": sc.cluster_id, "namespace": sc.namespace} for sc in scopes if sc.team_id == t.id
                ],
            }
        )
    return out


async def set_team(team_id: str, members: list[str], scopes: list[dict[str, str]]) -> None:
    """Substitui membros (por e-mail) e escopos do time."""
    async with db.session() as s:
        if not await s.get(Team, team_id):
            raise NotFound(team_id)
        emails = [e.strip().lower() for e in members]
        users = (await s.scalars(select(User).where(User.email.in_(emails)))).all() if emails else []
        missing = set(emails) - {u.email for u in users}
        if missing:
            raise ValueError(f"usuários inexistentes: {', '.join(sorted(missing))}")
        await s.execute(delete(TeamMember).where(TeamMember.team_id == team_id))
        await s.execute(delete(TeamScope).where(TeamScope.team_id == team_id))
        for u in users:
            s.add(TeamMember(team_id=team_id, user_id=u.id))
        for sc in scopes:
            s.add(TeamScope(team_id=team_id, cluster_id=sc.get("cluster") or "*", namespace=sc.get("namespace") or "*"))
        await s.commit()


async def delete_team(team_id: str) -> None:
    async with db.session() as s:
        team = await s.get(Team, team_id)
        if not team:
            raise NotFound(team_id)
        await s.delete(team)
        await s.commit()


async def principal_for(user: User) -> Principal:
    async with db.session() as s:
        rows = (
            await s.execute(
                select(TeamScope.cluster_id, TeamScope.namespace)
                .join(TeamMember, TeamMember.team_id == TeamScope.team_id)
                .where(TeamMember.user_id == user.id)
            )
        ).all()
    mfa = bool(user.totp_secret and not user.totp_secret.startswith(PENDING))
    return Principal(id=user.id, email=user.email, name=user.name, role=user.role, scopes=merge_scopes(rows), mfa=mfa)


# --------------------------------------------------------------------------- 2FA (TOTP)
def _totp(user: User) -> pyotp.TOTP | None:
    if not user.totp_secret:
        return None
    raw = user.totp_secret.removeprefix(PENDING)
    secret = crypto.decrypt(raw)
    return pyotp.TOTP(secret) if secret else None


async def totp_begin(user_id: str) -> dict[str, str]:
    """Gera um segredo pendente. Só passa a valer depois de confirmado com um código (totp_confirm)."""
    secret = pyotp.random_base32()
    async with db.session() as s:
        user = await s.get(User, user_id)
        if not user:
            raise NotFound(user_id)
        if user.totp_secret and not user.totp_secret.startswith(PENDING):
            raise ValueError("2FA já está ativo; desative antes de gerar outro")
        user.totp_secret = PENDING + crypto.encrypt(secret)
        await s.commit()
        email = user.email
    return {"secret": secret, "otpauthUri": pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)}


async def totp_confirm(user_id: str, code: str) -> None:
    async with db.session() as s:
        user = await s.get(User, user_id)
        if not user or not user.totp_secret or not user.totp_secret.startswith(PENDING):
            raise ValueError("nenhuma configuração de 2FA pendente")
        totp = _totp(user)
        if not totp or not totp.verify(code.strip(), valid_window=1):
            raise AuthError("mfa_invalid", "código inválido")
        user.totp_secret = user.totp_secret.removeprefix(PENDING)
        await s.commit()


async def totp_disable(user_id: str, code: str) -> None:
    async with db.session() as s:
        user = await s.get(User, user_id)
        if not user or not user.totp_secret:
            raise ValueError("2FA não está ativo")
        totp = _totp(user)
        if not user.totp_secret.startswith(PENDING) and (not totp or not totp.verify(code.strip(), valid_window=1)):
            raise AuthError("mfa_invalid", "código inválido")
        user.totp_secret = None
        await s.commit()


# --------------------------------------------------------------------------- login e sessões
@dataclass(frozen=True)
class LoginResult:
    token: str
    user: User


async def authenticate(email: str, password: str, code: str | None, ip: str | None) -> User:
    email = email.strip().lower()
    if ratelimit.is_locked(ip, email):
        raise AuthError("locked", "muitas tentativas; aguarde 15 minutos")
    async with db.session() as s:
        user = await s.scalar(select(User).where(User.email == email))
    password_ok = crypto.verify_password(user.password_hash if user else None, password)  # tempo constante
    if not user or not password_ok:
        ratelimit.record_failure(ip, email)
        raise AuthError("invalid", "e-mail ou senha incorretos")
    if not user.is_active:
        raise AuthError("inactive", "usuário desativado")
    totp = _totp(user) if user.totp_secret and not user.totp_secret.startswith(PENDING) else None
    if totp:
        if not code:
            raise AuthError("mfa_required", "informe o código do aplicativo autenticador")
        if not totp.verify(code.strip(), valid_window=1):
            ratelimit.record_failure(ip, email)
            raise AuthError("mfa_invalid", "código inválido")
    ratelimit.reset(ip, email)
    return user


async def create_session(user: User, ip: str | None, user_agent: str | None) -> str:
    token = crypto.new_token()
    async with db.session() as s:
        s.add(
            SessionRow(
                id=crypto.token_id(token),
                user_id=user.id,
                expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
                ip=ip,
                user_agent=(user_agent or "")[:255],
            )
        )
        row = await s.get(User, user.id)
        if row:
            row.last_login_at = utcnow()
        await s.commit()
    return token


async def resolve_session(token: str | None) -> Principal | None:
    if not token:
        return None
    async with db.session() as s:
        row = await s.get(SessionRow, crypto.token_id(token))
        if not row or row.revoked or (_aware(row.expires_at) or utcnow()) < utcnow():
            return None
        user = await s.get(User, row.user_id)
    if not user or not user.is_active:
        return None
    return await principal_for(user)


async def revoke_session(token: str | None) -> None:
    if not token:
        return
    async with db.session() as s:
        row = await s.get(SessionRow, crypto.token_id(token))
        if row:
            row.revoked = True
            await s.commit()


async def revoke_all(user_id: str) -> None:
    async with db.session() as s:
        for row in (await s.scalars(select(SessionRow).where(SessionRow.user_id == user_id))).all():
            row.revoked = True
        await s.commit()


async def find_or_create_sso_user(subject: str, email: str, name: str) -> User:
    """Login OIDC: liga pelo `sub`; na primeira vez, pelo e-mail; senão cria com o papel padrão."""
    email = email.strip().lower()
    async with db.session() as s:
        user = await s.scalar(select(User).where(User.oidc_subject == subject))
        if not user:
            user = await s.scalar(select(User).where(User.email == email))
            if user:
                user.oidc_subject = subject
            else:
                role = settings.oidc_default_role if settings.oidc_default_role in ROLES else "viewer"
                user = User(id=str(uuid.uuid4()), email=email, name=name or email, role=role, oidc_subject=subject)
                s.add(user)
            await s.commit()
    if not user.is_active:
        raise AuthError("inactive", "usuário desativado")
    return user
