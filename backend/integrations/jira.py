"""Jira Cloud: um ticket por incidente, atualizado em cada etapa e fechado quando o incidente termina.

Usa a API REST v3 (descrições e comentários em ADF) com e-mail + token de API. Grátis até 10 usuários.
Registra-se como canal em integrations.notify; uma falha do Jira nunca para o fluxo do incidente.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import settings

log = logging.getLogger("sentinel.jira")
PRIORITY = {"SEV1": "Highest", "SEV2": "High", "SEV3": "Medium", "SEV4": "Low"}
_transport: httpx.AsyncBaseTransport | None = None  # testes injetam um MockTransport
_account_ids: dict[str, str | None] = {}


def configured() -> bool:
    return bool(settings.jira_url and settings.jira_email and settings.jira_api_token and settings.jira_project)


def _client() -> httpx.AsyncClient:
    kwargs: dict[str, Any] = {
        "base_url": settings.jira_url,
        "auth": (settings.jira_email, settings.jira_api_token),
        "timeout": 15,
        "headers": {"Accept": "application/json"},
    }
    if _transport is not None:
        kwargs["transport"] = _transport
    return httpx.AsyncClient(**kwargs)


def adf(*paragraphs: str, mention: str | None = None) -> dict[str, Any]:
    """Atlassian Document Format mínimo: parágrafos de texto e, opcionalmente, uma menção."""
    content: list[dict[str, Any]] = []
    for text in paragraphs:
        if text:
            content.append({"type": "paragraph", "content": [{"type": "text", "text": text[:3000]}]})
    if mention:
        content.append({"type": "paragraph", "content": [{"type": "mention", "attrs": {"id": mention}}]})
    return {"type": "doc", "version": 1, "content": content or [{"type": "paragraph", "content": []}]}


def _summary(inc: Any) -> str:
    return f"[{inc.sev}] {inc.type} em {inc.namespace or 'cluster'}/{inc.deployment or inc.pod} ({inc.id})"[:250]


def _description(inc: Any) -> dict[str, Any]:
    rca = inc.rca or {}
    return adf(
        f"Incidente {inc.id} aberto pelo Hermes Sentinel.",
        f"Alvo: {inc.resourceKind}/{inc.pod} · namespace {inc.namespace or '-'} · cluster {inc.cluster}",
        f"Sinal: {inc.reason}",
        f"Causa (até agora): {rca.get('rootCause') or 'em investigação'}",
    )


async def _account_id(client: httpx.AsyncClient, email: str) -> str | None:
    if email not in _account_ids:
        resp = await client.get("/rest/api/3/user/search", params={"query": email})
        users = resp.json() if resp.status_code == 200 else []
        _account_ids[email] = users[0].get("accountId") if users else None
    return _account_ids[email]


async def _create(client: httpx.AsyncClient, inc: Any) -> None:
    fields = {
        "project": {"key": settings.jira_project},
        "issuetype": {"name": settings.jira_issue_type},
        "summary": _summary(inc),
        "description": _description(inc),
        "labels": ["hermes-sentinel", inc.sev.lower(), inc.type[:50].replace(" ", "-")],
        "priority": {"name": PRIORITY.get(inc.sev, "Medium")},
    }
    resp = await client.post("/rest/api/3/issue", json={"fields": fields})
    if resp.status_code == 400 and "priority" in resp.text:  # projetos sem o campo prioridade
        fields.pop("priority")
        resp = await client.post("/rest/api/3/issue", json={"fields": fields})
    resp.raise_for_status()
    key = resp.json()["key"]
    inc.ticket = {"system": "jira", "key": key, "url": f"{settings.jira_url}/browse/{key}"}
    log.info("Jira %s criado para %s", key, inc.id)


async def _assign(client: httpx.AsyncClient, key: str, emails: list[str]) -> str | None:
    for email in emails:
        account = await _account_id(client, email)
        if account:
            await client.put(f"/rest/api/3/issue/{key}/assignee", json={"accountId": account})
            return account
    return None


async def _transition_done(client: httpx.AsyncClient, key: str) -> None:
    resp = await client.get(f"/rest/api/3/issue/{key}/transitions")
    wanted = settings.jira_done_transition.lower()
    for t in resp.json().get("transitions", []) if resp.status_code == 200 else []:
        if t.get("name", "").lower() == wanted or t.get("to", {}).get("name", "").lower() == wanted:
            await client.post(f"/rest/api/3/issue/{key}/transitions", json={"transition": {"id": t["id"]}})
            return
    log.warning("Jira %s: transição '%s' não encontrada", key, settings.jira_done_transition)


async def channel(kind: str, inc: Any, text: str) -> None:
    """Canal de notificação: abre, comenta, atribui no escalonamento e fecha o ticket."""
    if not configured() or (inc.simulated and not settings.jira_include_simulated):
        return
    async with _client() as client:
        if not inc.ticket:
            await _create(client, inc)
        key = inc.ticket["key"]
        mention = None
        if kind in ("opened", "escalated") and inc.assignedTo:
            mention = await _assign(client, key, inc.assignedTo)
        await client.post(f"/rest/api/3/issue/{key}/comment", json={"body": adf(text, mention=mention)})
        if kind in ("resolved", "closed"):  # "failed" fica aberto: precisa de um humano
            await _transition_done(client, key)


def register() -> None:
    from integrations import notify

    if configured():
        notify.register("jira", channel)
        log.info("Jira ligado (projeto %s)", settings.jira_project)
