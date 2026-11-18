"""Sincroniza incidentes com GitHub Issues (só quando GITHUB_TOKEN está definido)."""

from __future__ import annotations

import logging

from config import settings
from schemas.events import Incident

log = logging.getLogger("sentinel.github")


def github_configured() -> bool:
    return bool(settings.github_token and settings.github_repo)


def create_issue(inc: Incident) -> str | None:
    """Cria a issue e devolve a URL. Síncrono — chame via asyncio.to_thread."""
    if not github_configured():
        return None
    from github import Auth, Github

    rca = inc.rca or {}
    gh = Github(auth=Auth.Token(settings.github_token), timeout=15)
    repo = gh.get_repo(settings.github_repo)
    title = f"[{inc.type}] {inc.namespace}/{inc.deployment or inc.pod} ({inc.id})"
    body = (
        f"**Incidente:** `{inc.id}`{' (simulado)' if inc.simulated else ''}\n\n"
        f"**Resumo:** {rca.get('stakeholderSummary', '-')}\n\n"
        f"**Causa raiz:** {rca.get('rootCause', '-')}\n\n"
        f"**Remediação:** `{inc.approval.command if inc.approval else '-'}`: {inc.remediationResult or 'pendente'}\n\n"
        "_Aberto automaticamente pelo agente ITSM do Hermes Sentinel._"
    )
    labels = []
    try:
        existing = {lb.name for lb in repo.get_labels()}
        labels = [lb for lb in ("incident", inc.type) if lb in existing]
    except Exception as exc:  # labels são opcionais: a issue sai sem elas
        log.debug("não consegui listar labels: %s", exc)
    issue = repo.create_issue(title=title, body=body, labels=labels)
    log.info("issue criada: %s", issue.html_url)
    return issue.html_url
