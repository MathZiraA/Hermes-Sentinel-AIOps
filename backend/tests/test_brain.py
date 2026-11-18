"""Hermes Brain: o vault forma um grafo ligado, aprende com as decisões e não deixa os bots escaparem dele."""

import pytest

from integrations import brain
from schemas.events import ApprovalRequest, Incident


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(brain, "root", lambda: tmp_path)
    brain._writes.clear()
    brain.ensure_vault()
    return tmp_path


def _inc(**kw):
    base = dict(
        id="INC-1",
        type="OOMKilled",
        namespace="stockflow",
        pod="relatorios-abc",
        deployment="relatorios",
        reason="exit 137",
        status="rejected",
        rca={
            "rootCause": "limite de 64Mi baixo",
            "evidence": ["exit 137"],
            "learning": "relatorios precisa de 256Mi",
            "runbooks": ["Runbook - OOMKilled.md"],
        },
    )
    base.update(kw)
    inc = Incident(**base)
    inc.approval = ApprovalRequest(
        incidentId=inc.id,
        action="rollout_restart",
        command="kubectl rollout restart x",
        description="",
        target="stockflow/relatorios",
    )
    return inc


def test_estrutura_e_grafo(vault):
    for f in brain.FOLDERS:
        assert (vault / f).is_dir()
    assert (vault / "00 - Index.md").exists() and (vault / ".obsidian/graph.json").exists()
    assert (vault / brain.TEAM / "Investigator.md").exists()


def test_incidente_liga_servico_padrao_e_aprendizado(vault):
    path = brain.write_incident(_inc(), ["10:00 detectado"])
    text = path.read_text()
    assert "[[relatorios]]" in text and "[[OOMKilled]]" in text and "[[Runbook - OOMKilled]]" in text
    pattern = (vault / brain.PATTERNS / "OOMKilled.md").read_text()
    assert path.stem in pattern and "relatorios precisa de 256Mi" in pattern
    assert path.stem in (vault / brain.SERVICES / "relatorios.md").read_text()


def test_licao_humana_entra_na_memoria_do_proximo_incidente(vault):
    brain.write_lesson(_inc(), "rejected", "reiniciar não resolve OOM; aumente o limite")
    assert brain.write_lesson(_inc(), "approved", "   ") is None  # sem motivo, sem lição
    memory = brain.related("OOMKilled", "relatorios")
    assert "aumente o limite" in memory


def test_busca_e_leitura(vault):
    brain.write_incident(_inc(), [])
    hits = brain.search("relatorios memória")
    assert hits and any(h["nota"] == "relatorios" for h in hits)
    folder, text = brain.read_note("[[OOMKilled]]".strip("[]"))
    assert folder == brain.PATTERNS and "# OOMKilled" in text


def test_bot_nao_escapa_do_vault(vault):
    p = brain.bot_note("investigator", "../../etc/passwd", "oi", links=["../x", "relatorios"])
    assert vault in p.resolve().parents and p.parent.name == "Investigator"
    with pytest.raises(FileNotFoundError):
        brain.read_note("../../../etc/passwd")


def test_limite_de_notas_por_hora(vault, monkeypatch):
    monkeypatch.setattr(brain, "NOTES_PER_HOUR", 2)
    brain.bot_note("monitor", "a", "1")
    brain.bot_note("monitor", "b", "2")
    with pytest.raises(PermissionError):
        brain.bot_note("monitor", "c", "3")


def test_migra_vault_antigo(tmp_path, monkeypatch):
    monkeypatch.setattr(brain, "root", lambda: tmp_path)
    (tmp_path / "Runbooks").mkdir()
    (tmp_path / "Runbooks/OOMKilled.md").write_text("---\nincident_types: [OOMKilled]\n---\n# Runbook")
    (tmp_path / "Post-Mortems").mkdir()
    (tmp_path / "Post-Mortems/2026-11-17-INC-1-X.md").write_text(
        "---\ntags: [post-mortem]\n---\n# Post-Mortem INC-1-ABC: OOMKilled em `stockflow/relatorios`\n"
    )
    brain.ensure_vault()
    assert (tmp_path / brain.RUNBOOKS / "Runbook - OOMKilled.md").exists()
    assert not (tmp_path / "Post-Mortems").exists()
    assert "INC-1-ABC" in (tmp_path / brain.SERVICES / "relatorios.md").read_text()
