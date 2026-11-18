"""Login com SSO (OpenID Connect): Authorization Code + PKCE, validando o id_token pelo JWKS do provedor.

Funciona com Keycloak, Google, Microsoft Entra ID, Okta e outros provedores OIDC.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from config import settings
from identity import crypto

STATE_TTL = 600  # segundos para concluir o login no provedor
_discovery: dict[str, Any] | None = None


class OidcError(Exception):
    pass


def enabled() -> bool:
    return bool(settings.oidc_issuer and settings.oidc_client_id)


async def discovery() -> dict[str, Any]:
    global _discovery
    if _discovery is None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.oidc_issuer}/.well-known/openid-configuration")
            resp.raise_for_status()
            _discovery = resp.json()
    return _discovery


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


async def authorization_url() -> tuple[str, str]:
    """Devolve (url do provedor, cookie cifrado com state/nonce/verifier)."""
    meta = await discovery()
    verifier, challenge = _pkce()
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    cookie = crypto.encrypt(json.dumps({"state": state, "nonce": nonce, "verifier": verifier, "t": time.time()}))
    return f"{meta['authorization_endpoint']}?{urlencode(params)}", cookie


async def complete(code: str, state: str, cookie: str | None) -> dict[str, str]:
    """Troca o código por tokens e devolve {sub, email, name} já validados."""
    raw = crypto.decrypt(cookie or "", ttl=STATE_TTL)
    if not raw:
        raise OidcError("sessão de login expirada; tente de novo")
    saved = json.loads(raw)
    if not secrets.compare_digest(saved["state"], state):
        raise OidcError("state inválido")
    meta = await discovery()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            meta["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "code_verifier": saved["verifier"],
            },
        )
    if resp.status_code != 200:
        raise OidcError(f"o provedor recusou o código ({resp.status_code})")
    id_token = resp.json().get("id_token")
    if not id_token:
        raise OidcError("o provedor não devolveu id_token")
    signing_key = jwt.PyJWKClient(meta["jwks_uri"]).get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=meta.get("id_token_signing_alg_values_supported", ["RS256"]),
        audience=settings.oidc_client_id,
        issuer=meta.get("issuer", settings.oidc_issuer),
    )
    if not secrets.compare_digest(claims.get("nonce", ""), saved["nonce"]):
        raise OidcError("nonce inválido")
    email = (claims.get("email") or "").lower()
    if not email or claims.get("email_verified") is False:
        raise OidcError("o provedor não confirmou o e-mail")
    domain = email.rsplit("@", 1)[-1]
    if settings.oidc_allowed_domains and domain not in settings.oidc_allowed_domains:
        raise OidcError(f"domínio {domain} não autorizado")
    return {"sub": str(claims["sub"]), "email": email, "name": claims.get("name") or email}
