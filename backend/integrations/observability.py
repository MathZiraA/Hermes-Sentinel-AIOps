"""Grafana (links), Loki (logs além do que o pod guarda) e GitHub (commits do deploy)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from config import settings

log = logging.getLogger("sentinel.observability")
_transport: httpx.AsyncBaseTransport | None = None  # testes injetam um MockTransport


def _parse(ts: str | None) -> datetime:
    if not ts:
        return datetime.now(UTC)
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# --------------------------------------------------------------------------- Grafana
def grafana_link(inc: Any) -> str | None:
    """Painel do Grafana no intervalo do incidente (30 min antes até agora/resolução)."""
    if not settings.grafana_url:
        return None
    start = _parse(inc.detectedAt) - timedelta(minutes=30)
    end = _parse(inc.resolvedAt) + timedelta(minutes=10) if inc.resolvedAt else datetime.now(UTC)
    params = {
        "from": int(start.timestamp() * 1000),
        "to": int(end.timestamp() * 1000),
        "var-namespace": inc.namespace,
        "var-workload": inc.deployment or inc.pod,
    }
    if settings.grafana_dashboard_uid:
        return f"{settings.grafana_url}/d/{settings.grafana_dashboard_uid}?{urlencode(params)}"
    return f"{settings.grafana_url}/explore?{urlencode({'from': params['from'], 'to': params['to']})}"


# --------------------------------------------------------------------------- Loki
def loki_configured() -> bool:
    return bool(settings.loki_url)


def loki_selector(namespace: str, workload: str) -> str:
    return settings.loki_selector.replace("{namespace}", namespace).replace("{workload}", workload)


def loki_explore_link(inc: Any) -> str | None:
    if not (settings.grafana_url and settings.loki_url):
        return None
    query = loki_selector(inc.namespace, inc.deployment or inc.pod)
    return f"{settings.grafana_url}/explore?left={quote(f'{{"queries":[{{"expr":{query!r}}}]}}')}"


async def loki_logs(namespace: str, workload: str, minutes: int = 30, contains: str = "", limit: int = 200) -> str:
    """Logs do workload no Loki: sobrevivem ao pod (que pode já ter sido recriado)."""
    if not loki_configured():
        raise RuntimeError("Loki não configurado (LOKI_URL)")
    end = datetime.now(UTC)
    start = end - timedelta(minutes=max(1, min(minutes, 24 * 60)))
    query = loki_selector(namespace, workload)
    if contains:
        query += f' |= "{contains.replace(chr(34), "")}"'
    headers = {"Authorization": f"Bearer {settings.loki_token}"} if settings.loki_token else {}
    kwargs: dict[str, Any] = {"timeout": 15, "headers": headers}
    if _transport is not None:
        kwargs["transport"] = _transport
    async with httpx.AsyncClient(**kwargs) as client:
        resp = await client.get(
            f"{settings.loki_url}/loki/api/v1/query_range",
            params={
                "query": query,
                "start": int(start.timestamp() * 1e9),
                "end": int(end.timestamp() * 1e9),
                "limit": max(1, min(limit, 500)),
                "direction": "backward",
            },
        )
    resp.raise_for_status()
    lines: list[tuple[str, str]] = []
    for stream in resp.json().get("data", {}).get("result", []):
        lines += [(ts, line) for ts, line in stream.get("values", [])]
    lines.sort()
    return "\n".join(line for _, line in lines[-limit:]) or "(nenhuma linha no período)"


# --------------------------------------------------------------------------- GitHub (commits do deploy)
def _repo_for(workload: str) -> str | None:
    """GITHUB_DEPLOY_REPOS="pedidos=org/pedidos,pagamentos=org/pagamentos"; senão, GITHUB_REPO."""
    for item in settings.github_deploy_repos.split(","):
        name, _, repo = item.partition("=")
        if name.strip() == workload and repo.strip():
            return repo.strip()
    return None


def deploy_commits(workload: str, since: str | None, limit: int = 5) -> list[dict[str, str]]:
    """Commits do repositório do workload desde pouco antes do rollout (síncrono: chame em thread)."""
    repo_name = _repo_for(workload)
    if not (settings.github_token and repo_name):
        return []
    from github import Auth, Github

    gh = Github(auth=Auth.Token(settings.github_token), timeout=15)
    start = _parse(since) - timedelta(hours=6)
    out = []
    for c in gh.get_repo(repo_name).get_commits(since=start)[:limit]:
        out.append(
            {
                "sha": c.sha[:7],
                "message": (c.commit.message or "").splitlines()[0][:120],
                "author": c.commit.author.name if c.commit.author else "?",
                "url": c.html_url,
            }
        )
    return out


def status() -> dict[str, dict[str, Any]]:
    from integrations import jira

    return {
        "jira": {"ok": jira.configured(), "detail": settings.jira_project or "JIRA_* não definido"},
        "zabbix": {
            "ok": bool(settings.zabbix_webhook_token),
            "detail": "webhook /api/integrations/zabbix"
            if settings.zabbix_webhook_token
            else "ZABBIX_WEBHOOK_TOKEN não definido",
        },
        "grafana": {"ok": bool(settings.grafana_url), "detail": settings.grafana_url or "GRAFANA_URL não definido"},
        "loki": {"ok": loki_configured(), "detail": settings.loki_url or "LOKI_URL não definido"},
        "githubDeploys": {
            "ok": bool(settings.github_token and settings.github_deploy_repos),
            "detail": "GITHUB_DEPLOY_REPOS" if settings.github_deploy_repos else "não configurado",
        },
    }
