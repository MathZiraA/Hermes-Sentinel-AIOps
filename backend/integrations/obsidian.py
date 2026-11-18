"""Obsidian Vault local: leitura de Runbooks e escrita de Post-Mortems em Markdown."""

from __future__ import annotations

import re
from pathlib import Path

from config import settings
from schemas.events import Incident

MAX_RUNBOOK_CHARS = 3500  # limita o contexto enviado à IA (quota)


def _frontmatter_types(text: str) -> set[str]:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return set()
    t = re.search(r"incident_types:\s*\[(.*?)\]", m.group(1))
    return {x.strip() for x in t.group(1).split(",")} if t else set()


def list_runbooks() -> list[Path]:
    d = settings.runbooks_dir
    return sorted(d.glob("*.md")) if d.is_dir() else []


def find_runbooks(incident_type: str) -> list[tuple[str, str]]:
    """Runbooks cujo frontmatter `incident_types` ou nome de arquivo casam com o incidente."""
    hits: list[tuple[str, str]] = []
    for path in list_runbooks():
        text = path.read_text(encoding="utf-8", errors="replace")
        stem = path.stem.lower().removeprefix("runbook - ")
        if incident_type in _frontmatter_types(text) or stem == incident_type.lower():
            hits.append((path.name, text[:MAX_RUNBOOK_CHARS]))
    return hits


def vault_status() -> dict:
    from integrations import brain

    return brain.status()


def write_postmortem(inc: Incident, timeline: list[str]) -> Path:
    """Compatibilidade: o post-mortem agora é a nota do incidente no Hermes Brain."""
    from integrations import brain

    return brain.write_incident(inc, timeline)
