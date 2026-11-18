"""Fase 2: login, sessões, papéis, escopo por time, 2FA, força bruta, CSRF e regras de administração."""

from types import SimpleNamespace as NS

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient

from db import repository as repo
from domain.permissions import Principal, Scope, has_permission
from identity import crypto, ratelimit, service
from schemas.events import ApprovalRequest, Incident

ADMIN_PW = "Admin-Senha-Forte-1"
USER_PW = "Usuario-Senha-Forte-2"
ORIGIN = {"Origin": "http://localhost:3000"}


def test_papeis_e_escopo():
    assert has_permission("operator", "incidents:decide")
    assert not has_permission("viewer", "incidents:decide")
    assert has_permission("auditor", "audit:read") and not has_permission("operator", "audit:read")
    p = Principal(id="1", email="a", name="a", role="viewer", scopes=(Scope("local", "stockflow"),))
    assert p.sees("local", "stockflow") and not p.sees("local", "financeiro") and not p.unrestricted


def test_politica_de_senha_e_hash():
    with pytest.raises(crypto.WeakPassword):
        crypto.check_password_policy("curta")
    with pytest.raises(crypto.WeakPassword):
        crypto.check_password_policy("semnumerosnemmaiusculas")
    h = crypto.hash_password(ADMIN_PW)
    assert h.startswith("$argon2id$") and crypto.verify_password(h, ADMIN_PW) and not crypto.verify_password(h, "x")


@pytest.fixture()
async def app(database, tmp_path, monkeypatch):
    import main
    from agents import orchestrator as orch_mod
    from integrations import brain

    monkeypatch.setattr(crypto, "secret_key", lambda: b"chave-de-teste")
    monkeypatch.setattr(orch_mod, "STEP", 0)
    monkeypatch.setattr(brain, "root", lambda: tmp_path / "brain")
    ratelimit.clear_all()
    orch_mod.orchestrator.incidents.clear()
    await repo.ensure_cluster("local", "local")
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000", headers=ORIGIN) as client:
        yield client, orch_mod.orchestrator


async def _login(client, email, password, code=None):
    body = {"email": email, "password": password}
    if code:
        body["code"] = code
    return await client.post("/api/auth/login", json=body)


async def _setup_admin(client):
    r = await client.post("/api/auth/setup", json={"email": "admin@empresa.com", "name": "Admin", "password": ADMIN_PW})
    assert r.status_code == 200
    return r


async def test_primeira_configuracao_cria_admin_uma_unica_vez(app):
    client, _ = app
    assert (await client.get("/api/auth/config")).json()["needsSetup"] is True
    r = await _setup_admin(client)
    assert r.json()["role"] == "admin" and "sentinel_session" in r.cookies
    again = await client.post("/api/auth/setup", json={"email": "x@y.com", "name": "X", "password": ADMIN_PW})
    assert again.status_code == 409


async def test_rotas_exigem_login_e_logout_revoga(app):
    client, _ = app
    client.cookies.clear()
    assert (await client.get("/api/incidents")).status_code == 401
    assert (await client.get("/api/healthz")).status_code == 200  # liveness continua pública
    await _setup_admin(client)
    assert (await client.get("/api/auth/me")).json()["email"] == "admin@empresa.com"
    assert (await client.post("/api/auth/logout")).status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_visualizador_nao_aprova_e_so_ve_o_proprio_escopo(app):
    client, orch = app
    await _setup_admin(client)
    viewer = (
        await client.post(
            "/api/admin/users",
            json={"email": "vi@empresa.com", "name": "Vi", "role": "viewer", "password": USER_PW},
        )
    ).json()
    team = (await client.post("/api/admin/teams", json={"name": "Financeiro"})).json()
    await client.put(
        f"/api/admin/teams/{team['id']}",
        json={"members": ["vi@empresa.com"], "scopes": [{"cluster": "local", "namespace": "financeiro"}]},
    )
    # um incidente fora do escopo do visualizador
    inc = Incident(
        id="INC-S",
        type="OOMKilled",
        namespace="stockflow",
        pod="p",
        deployment="d",
        reason="r",
        simulated=True,
        status="detected",
    )
    await orch._register(inc)
    await orch._set_status(inc, "investigating")
    inc.approval = ApprovalRequest(incidentId=inc.id, action="none", command="-", description="", target="t")
    await orch._set_status(inc, "waiting_approval")

    client.cookies.clear()
    assert (await _login(client, "vi@empresa.com", USER_PW)).status_code == 200
    listed = (await client.get("/api/incidents")).json()
    assert listed["total"] == 0
    assert (await client.get("/api/incidents/INC-S")).status_code == 404
    assert (await client.post("/api/agents/approve/INC-S")).status_code == 403
    assert (await client.get("/api/audit")).status_code == 403
    assert viewer["role"] == "viewer"


async def test_2fa_exige_codigo_no_login(app):
    client, _ = app
    await _setup_admin(client)
    secret = (await client.post("/api/auth/totp/setup")).json()["secret"]
    assert (await client.post("/api/auth/totp/enable", json={"code": "000000"})).status_code == 400
    assert (await client.post("/api/auth/totp/enable", json={"code": pyotp.TOTP(secret).now()})).status_code == 200
    client.cookies.clear()
    r = await _login(client, "admin@empresa.com", ADMIN_PW)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "mfa_required"
    r = await _login(client, "admin@empresa.com", ADMIN_PW, pyotp.TOTP(secret).now())
    assert r.status_code == 200 and r.json()["mfa"] is True


async def test_forca_bruta_bloqueia_e_fica_na_auditoria(app):
    client, _ = app
    await _setup_admin(client)
    client.cookies.clear()
    codes = [(await _login(client, "admin@empresa.com", "errada")).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    assert (await _login(client, "admin@empresa.com", ADMIN_PW)).status_code == 429  # bloqueado mesmo com a certa
    entries, _ = await repo.list_audit(limit=20)
    assert sum(e["action"] == "auth.login_failed" for e in entries) >= 5


async def test_escrita_de_outra_origem_e_recusada(app):
    client, _ = app
    r = await client.post(
        "/api/auth/setup",
        json={"email": "a@b.com", "name": "A", "password": ADMIN_PW},
        headers={"Origin": "https://site-malicioso.example"},
    )
    assert r.status_code == 403


async def test_nao_rebaixa_o_ultimo_admin_e_mudanca_derruba_sessoes(app):
    client, _ = app
    me = (await _setup_admin(client)).json()
    assert (await client.patch(f"/api/admin/users/{me['id']}", json={"role": "viewer"})).status_code == 422
    other = (
        await client.post(
            "/api/admin/users", json={"email": "op@empresa.com", "name": "Op", "role": "operator", "password": USER_PW}
        )
    ).json()
    admin_cookie = client.cookies.get("sentinel_session")
    client.cookies.clear()
    await _login(client, "op@empresa.com", USER_PW)
    assert (await client.get("/api/auth/me")).status_code == 200
    op_cookie = client.cookies.get("sentinel_session")
    client.cookies.set("sentinel_session", admin_cookie)
    await client.patch(f"/api/admin/users/{other['id']}", json={"active": False})
    client.cookies.set("sentinel_session", op_cookie)
    assert (await client.get("/api/auth/me")).status_code == 401  # sessão do desativado caiu


async def test_sso_cria_usuario_com_papel_padrao(database, monkeypatch):
    monkeypatch.setattr(service, "settings", NS(oidc_default_role="viewer"))
    user = await service.find_or_create_sso_user("sub-123", "Novo@Empresa.com", "Novo")
    again = await service.find_or_create_sso_user("sub-123", "novo@empresa.com", "Novo")
    assert user.id == again.id and user.role == "viewer" and user.email == "novo@empresa.com"
