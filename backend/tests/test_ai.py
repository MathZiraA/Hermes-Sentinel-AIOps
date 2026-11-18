"""Fase 6: provedor trocável, orçamento diário, avaliação do diagnóstico e índice do Hermes Brain."""

import dataclasses
import json
from types import SimpleNamespace as NS

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from config import settings
from db import ai
from db import repository as repo
from integrations import brain, brain_index, hermes_client
from schemas.events import Incident


def _inc(**kw) -> Incident:
    base = dict(
        id="INC-R",
        type="OOMKilled",
        namespace="stockflow",
        pod="relatorios-x",
        deployment="relatorios",
        reason="exit 137",
        logs="java.lang.OutOfMemoryError",
        events="exit 137",
    )
    base.update(kw)
    return Incident(**base)


@pytest.fixture()
def openai_provider(monkeypatch):
    cfg = dataclasses.replace(
        settings,
        ai_provider="openai",
        ai_base_url="http://llm.local/v1",
        ai_model="modelo-x",
        ai_api_key="k",
        ai_daily_call_limit=2,
        ai_min_interval=0,
    )
    monkeypatch.setattr(hermes_client, "settings", cfg)
    monkeypatch.setattr(ai, "settings", cfg)
    client = hermes_client.HermesClient()
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        rca = {
            "rootCause": "limite de 64Mi baixo",
            "evidence": ["exit 137"],
            "confidence": "alta",
            "recommendedAction": {
                "type": "set_resources",
                "container": "relatorios",
                "memory_limit": "256Mi",
                "reason": "subir o limite",
            },
            "stakeholderSummary": "relatórios sem memória",
            "followUps": [],
            "learning": "64Mi não basta",
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(rca)}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 40},
            },
        )

    client._transport = httpx.MockTransport(handler)
    return client, seen


async def test_provedor_compativel_com_openai_e_orcamento_diario(database, openai_provider):
    client, seen = openai_provider
    rca = await client.diagnose(_inc(), [])
    assert rca["source"] == "openai-compatible" and rca["recommendedAction"]["type"] == "set_resources"
    assert seen[0]["model"] == "modelo-x"
    await client.diagnose(_inc(), [])
    blocked = await client.diagnose(_inc(), [])  # terceira chamada: limite de 2 por dia
    assert blocked["source"] == "fallback" and "orçamento" in blocked["fallbackReason"]
    today = await ai.totals_today()
    assert today == {"calls": 2, "tokens": 320, "blocked": 1}
    usage = await ai.usage(7)
    assert usage["days"][0]["tokensIn"] == 240 and usage["limits"]["callsPerDay"] == 2


async def test_indice_busca_sem_acento_e_ranqueia_pelo_titulo(database, tmp_path, monkeypatch):
    monkeypatch.setattr(brain, "root", lambda: tmp_path)
    brain.ensure_vault()
    (tmp_path / brain.SERVICES / "relatorios.md").write_text("# relatorios\n\nGera relatórios de pedidos em memória.")
    (tmp_path / brain.PATTERNS / "OOMKilled.md").write_text("# OOMKilled\n\nMemória acima do limite do container.")
    first = await brain_index.sync()
    assert first["indexed"] >= 2 and (await brain_index.sync())["indexed"] == 0  # incremental
    hits = await brain_index.search("memoria relatorios")
    assert hits[0]["nota"] == "relatorios"
    (tmp_path / brain.SERVICES / "relatorios.md").unlink()
    assert (await brain_index.sync())["removed"] == 1


async def test_avaliacao_do_diagnostico_gera_licao_e_entra_no_relatorio(database, tmp_path, monkeypatch):
    from api import deps, incidents

    monkeypatch.setattr(deps, "settings", NS(auth_enabled=False))
    monkeypatch.setattr(brain, "root", lambda: tmp_path)
    await repo.ensure_cluster("local", "local")
    inc = _inc(
        rca={"rootCause": "vazamento", "source": "hermes-agent+mcp"},
        status="resolved",
        resolvedAt="2026-11-18T12:30:00+00:00",
    )
    await repo.save_incident(inc)
    app = FastAPI()
    app.include_router(incidents.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.post("/api/incidents/INC-R/rating", json={"correct": False})).status_code == 422
        r = await client.post("/api/incidents/INC-R/rating", json={"correct": False, "note": "era limite baixo"})
        assert r.status_code == 200 and r.json()["rcaRating"]["correct"] is False
    lessons = list((tmp_path / brain.LESSONS).glob("Licao - diagnostico errado*.md"))
    assert lessons and "era limite baixo" in lessons[0].read_text()
    summary = await repo.summary(days=3650)
    assert summary["rca"] == {"rated": 1, "correct": 0, "accuracy": 0.0, "bySource": {"hermes-agent+mcp": 1}}
