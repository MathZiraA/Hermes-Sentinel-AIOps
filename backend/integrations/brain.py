"""Hermes Brain: a memória de longo prazo do time, um vault Obsidian no notebook.

Cada incidente vira uma nota ligada (por [[wikilinks]]) ao Serviço, ao Padrão de falha,
ao Runbook e aos bots que trabalharam nele. As decisões humanas viram Lições. Os bots
escrevem no próprio Diário. Abra a pasta no Obsidian e o grafo mostra o cérebro crescendo.

Os bots chegam aqui pelas ferramentas MCP (memoria_buscar, memoria_ler, memoria_registrar,
runbook_rascunho). Tudo fica preso dentro do vault: nomes saneados, caminhos verificados,
tamanho limitado e limite de notas por hora.
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from config import settings

INDEX = "00 - Index.md"
TEAM, SERVICES, PATTERNS, INCIDENTS = "01 - Equipe", "02 - Serviços", "03 - Padrões", "04 - Incidentes"
LESSONS, RUNBOOKS, DIARY, CLUSTER = "05 - Lições", "06 - Runbooks", "07 - Diário dos Bots", "08 - Cluster"
DRAFTS = f"{RUNBOOKS}/Rascunhos"
FOLDERS = (TEAM, SERVICES, PATTERNS, INCIDENTS, LESSONS, RUNBOOKS, DRAFTS, DIARY, CLUSTER)

BOTS = {
    "monitor": ("Monitor", "Vigia o cluster 24/7 sem IA e dispara os alertas."),
    "supervisor": ("Supervisor", "Coordena o time e traduz o incidente para quem não é técnico."),
    "investigator": ("Investigator", "Acha a causa raiz: logs, eventos, recursos, métricas e a memória do time."),
    "executor": ("Executor", "Propõe e aplica correções, sempre depois da aprovação humana."),
    "itsm": ("ITSM", "Kanban, post-mortems e a organização deste cérebro."),
    "hermes": ("Hermes", "O agente no VPS que dá voz e raciocínio aos cinco bots."),
}
NODE_KINDS = {"Node"}
HUBS = (
    (SERVICES, "Serviços", "Uma nota por workload do cluster, com o histórico de falhas e as suas notas."),
    (PATTERNS, "Padrões", "Uma nota por tipo de falha, com o que o time já aprendeu sobre ele."),
    (INCIDENTS, "Incidentes", "Todos os incidentes, com causa, evidências e a decisão humana."),
    (LESSONS, "Lições", "Decisões e regras humanas. Os bots leem isto antes de investigar."),
    (RUNBOOKS, "Runbooks", "Procedimentos oficiais. Rascunhos dos bots ficam em Rascunhos/ até você aprovar."),
    (DIARY, "Diário dos Bots", "O que cada bot decidiu anotar enquanto trabalhava."),
    (CLUSTER, "Cluster", "Nós e infraestrutura do cluster."),
)
MAX_NOTE_CHARS = 6000
MAX_CONTEXT_CHARS = 1800
NOTES_PER_HOUR = 30

_lock = threading.Lock()
_writes: dict[str, list[float]] = {}


# --------------------------------------------------------------------------- utilidades
def root() -> Path:
    return settings.obsidian_vault_path


def safe_title(text: str, max_len: int = 80) -> str:
    """Nome de arquivo seguro (mantém acentos, tira barras, pontos iniciais e símbolos)."""
    text = unicodedata.normalize("NFC", str(text or ""))
    text = re.sub(r"[^\w\s\-–.,()áéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]", " ", text, flags=re.U)
    text = re.sub(r"\s+", " ", text).strip(" .-")
    return text[:max_len].strip() or "sem título"


def _inside(path: Path) -> Path:
    p = path.resolve()
    r = root().resolve()
    if p != r and r not in p.parents:
        raise ValueError("caminho fora do cérebro")
    return p


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _write_new(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _append_to_section(path: Path, header: str, line: str) -> None:
    """Insere `line` no fim da seção `header` (cria a seção se faltar)."""
    text = path.read_text(encoding="utf-8")
    if line.strip() and line.strip() in text:
        return
    idx = text.find(header)
    if idx < 0:
        text = text.rstrip() + f"\n\n{header}\n{line}\n"
    else:
        nxt = text.find("\n## ", idx + len(header))
        end = len(text) if nxt < 0 else nxt
        text = text[:end].rstrip() + f"\n{line}\n" + text[end:]
    path.write_text(text, encoding="utf-8")


def _frontmatter(**kv: Any) -> str:
    lines = []
    for k, v in kv.items():
        if isinstance(v, (list, tuple)):
            v = "[" + ", ".join(str(x) for x in v) + "]"
        lines.append(f"{k}: {v}")
    return "---\n" + "\n".join(lines) + "\n---\n"


# --------------------------------------------------------------------------- estrutura do vault
def ensure_vault() -> None:
    with _lock:
        r = root()
        for f in FOLDERS:
            (r / f).mkdir(parents=True, exist_ok=True)
        for key, (name, role) in BOTS.items():
            p = r / TEAM / f"{name}.md"
            if not p.exists():
                diary = f"[[{DIARY}/{name}|Diário do {name}]]" if key != "hermes" else "—"
                _write_new(
                    p,
                    _frontmatter(tags=["equipe", "bot"], bot=key)
                    + f"\n# {name}\n\n{role}\n\n- Diário: {diary}\n\n## Relacionado\n[[Equipe]] · [[00 - Index]]\n",
                )
            (r / DIARY / name).mkdir(parents=True, exist_ok=True)
        team = r / TEAM / "Equipe.md"
        if not team.exists():
            _write_new(
                team,
                "# Equipe\n\n"
                + "\n".join(f"- [[{n}]]: {d}" for n, d in BOTS.values())
                + "\n\n## Relacionado\n[[00 - Index]]\n",
            )
        for folder, hub, desc in HUBS:
            hp = r / folder / f"{hub}.md"
            if not hp.exists():
                _write_new(hp, f"# {hub}\n\n{desc}\n\n## Relacionado\n[[00 - Index]]\n")
        if not (r / INDEX).exists():
            _write_new(r / INDEX, _index_text())
        _obsidian_config(r)
        _migrate_legacy(r)


def _index_text() -> str:
    return f"""# Hermes Brain — Index

> A memória do time Hermes Sentinel. Cada incidente vira nota, se liga ao serviço, ao padrão de falha e ao
> runbook, e as suas decisões viram lições que os bots leem antes de investigar. **Edite à vontade**: corrigir
> um runbook ou escrever uma lição aqui ensina o time na hora.

---

## Time
- [[Equipe]]: [[Monitor]] · [[Supervisor]] · [[Investigator]] · [[Executor]] · [[ITSM]] · [[Hermes]]

## Hubs
- [[Serviços]] · [[Padrões]] · [[Incidentes]] · [[Lições]] · [[Runbooks]] · [[Diário dos Bots]] · [[Cluster]]

## Memória
- **Serviços** (`{SERVICES}`): um por workload, com o histórico de falhas
- **Padrões** (`{PATTERNS}`): um por tipo de falha, com o que já aprendemos
- **Incidentes** (`{INCIDENTS}`): um por incidente, com causa, evidências e decisão
- **Lições** (`{LESSONS}`): suas aprovações e rejeições, com o motivo. É assim que você treina o time
- **Runbooks** (`{RUNBOOKS}`): procedimentos. Os bots escrevem rascunhos em `{DRAFTS}`; mova para cima para aprovar
- **Diário dos Bots** (`{DIARY}`): o que cada bot decidiu anotar
- **Cluster** (`{CLUSTER}`): nós e infraestrutura

## Como treinar
1. Ao aprovar/rejeitar uma correção, escreva o **motivo**: vira uma Lição.
2. Revise os rascunhos de runbook e mova os bons para `{RUNBOOKS}`.
3. Escreva regras suas em `{LESSONS}` (ex.: "nunca reiniciar o mysql em horário comercial").
"""


def _obsidian_config(r: Path) -> None:
    cfg = r / ".obsidian"
    cfg.mkdir(exist_ok=True)
    graph = cfg / "graph.json"
    if not graph.exists():
        groups = [
            (INCIDENTS, 0xE5484D),
            (PATTERNS, 0xF76B15),
            (SERVICES, 0x3E63DD),
            (LESSONS, 0x30A46C),
            (RUNBOOKS, 0x8E4EC6),
            (TEAM, 0xFFC53D),
            (DIARY, 0x8B8D98),
            (CLUSTER, 0x12A594),
        ]
        graph.write_text(
            json.dumps(
                {
                    "showOrphans": True,
                    "showArrow": False,
                    "showTags": False,
                    "hideUnresolved": False,
                    "colorGroups": [{"query": f'path:"{p}"', "color": {"a": 1, "rgb": c}} for p, c in groups],
                    "centerStrength": 0.52,
                    "repelStrength": 10,
                    "linkStrength": 1,
                    "linkDistance": 250,
                    "scale": 0.5,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    app = cfg / "app.json"
    if not app.exists():
        app.write_text(json.dumps({"newLinkFormat": "shortest", "useMarkdownLinks": False}, indent=2), encoding="utf-8")


def _migrate_legacy(r: Path) -> None:
    """Runbooks/ e Post-Mortems/ da versão antiga → estrutura nova, já ligados no grafo."""
    old_rb = r / "Runbooks"
    if old_rb.is_dir():
        for f in old_rb.glob("*.md"):
            dest = r / RUNBOOKS / f"Runbook - {f.stem}.md"
            if not dest.exists():
                f.rename(dest)
                _ensure_pattern(f.stem)
        _rmdir_if_empty(old_rb)
    old_pm = r / "Post-Mortems"
    if old_pm.is_dir():
        for f in sorted(old_pm.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            m = re.search(r"# Post-Mortem (INC-[\w-]+): (\w+) em `([\w.-]+)/([\w.-]+)`", text)
            if m:
                inc_id, itype, ns, target = m.groups()
                text = text.replace("tags: [post-mortem", "tags: [incidente, post-mortem", 1)
                text = text.rstrip() + f"\n\n## Relacionado\n[[{itype}]] · [[{target}]] · [[Incidentes]]\n"
                dest = r / INCIDENTS / f"{f.stem[:10]} {inc_id} {itype}.md"
                _write_new(dest, text)
                f.unlink()
                _ensure_pattern(itype)
                _ensure_service(ns, target, "Pod")
                line = f"- [[{dest.stem}]]: {itype}"
                _append_to_section(r / PATTERNS / f"{itype}.md", "## Casos", line)
                _append_to_section(r / SERVICES / f"{target}.md", "## Histórico", line)
            else:
                f.rename(r / INCIDENTS / f.name)
        _rmdir_if_empty(old_pm)


def _rmdir_if_empty(d: Path) -> None:
    for junk in d.glob(".gitkeep"):
        junk.unlink()
    with contextlib.suppress(OSError):  # pasta antiga ainda tem arquivos: fica onde está
        d.rmdir()


def _ensure_pattern(itype: str) -> Path:
    p = root() / PATTERNS / f"{safe_title(itype)}.md"
    if not p.exists():
        rb = (
            f"[[Runbook - {itype}]]"
            if (root() / RUNBOOKS / f"Runbook - {itype}.md").exists()
            else "(ainda sem runbook)"
        )
        _write_new(
            p,
            _frontmatter(tags=["padrão", "falha"], tipo=itype)
            + f"\n# {itype}\n\nPadrão de falha visto no cluster.\n\n- Runbook: {rb}\n\n"
            "## O que aprendemos\n\n## Casos\n\n## Relacionado\n[[Padrões]] · [[00 - Index]]\n",
        )
    return p


def _ensure_service(ns: str, name: str, kind: str) -> Path:
    folder = CLUSTER if kind in NODE_KINDS else SERVICES
    p = root() / folder / f"{safe_title(name)}.md"
    if not p.exists():
        _write_new(
            p,
            _frontmatter(
                tags=["serviço" if folder == SERVICES else "cluster", kind.lower()], namespace=ns or "-", kind=kind
            )
            + f"\n# {name}\n\n`{kind}` em `{ns or 'cluster'}`.\n\n## Notas\n\n## Histórico\n\n"
            f"## Relacionado\n[[{'Serviços' if folder == SERVICES else 'Cluster'}]] · [[00 - Index]]\n",
        )
    return p


# --------------------------------------------------------------------------- escrita pelo fluxo do Sentinel
def write_incident(inc: Any, timeline: list[str]) -> Path:
    """Nota do incidente + atualiza Serviço e Padrão (é isto que forma o grafo)."""
    ensure_vault()
    with _lock:
        rca = inc.rca or {}
        target = inc.deployment or inc.pod
        kind = getattr(inc, "resourceKind", "Pod") or "Pod"
        _ensure_pattern(inc.type)
        _ensure_service(inc.namespace, target, kind)
        day = _today()
        name = f"{day} {inc.id} {safe_title(inc.type, 40)}"
        bots = ["Monitor", "Supervisor", "Investigator", "Executor", "ITSM"]
        runbooks = [f"[[{Path(n).stem}]]" for n in rca.get("runbooks", [])] or ["(nenhum)"]
        evidence = "\n".join(f"- {e}" for e in rca.get("evidence", [])) or "- (sem evidências registradas)"
        who = getattr(inc, "decisionBy", None) or "o operador"
        decision = {
            "resolved": f"aprovada por {who} e aplicada",
            "postmortem": f"aprovada por {who} e aplicada",
            "closed": f"rejeitada por {who}",
            "rejected": f"rejeitada por {who}",
            "failed": "aprovada, mas falhou",
        }.get(inc.status, inc.status)
        body = (
            _frontmatter(
                tags=["incidente", safe_title(inc.type, 40).replace(" ", "-")],
                incidente=inc.id,
                tipo=inc.type,
                status=inc.status,
                simulado=str(inc.simulated).lower(),
                data=day,
                confianca=rca.get("confidence", "-"),
                fonte=rca.get("source", "-"),
            )
            + f"""
# {inc.id}: {inc.type} em [[{target}]]

> {rca.get("stakeholderSummary", "")}

| Campo | Valor |
|---|---|
| Padrão | [[{inc.type}]] |
| Alvo | `{inc.namespace}/{inc.pod}` ({kind}) |
| Sinal | {inc.reason} |
| Detectado | {inc.detectedAt} |
| Correção | `{inc.approval.command if inc.approval else "-"}` ({decision}) |
| Resultado | {inc.remediationResult or "-"} |

## Causa raiz
{rca.get("rootCause", "(não determinada)")}

## Evidências
{evidence}

## O que aprendemos
{rca.get("learning") or "-"}

## Linha do tempo
{chr(10).join(f"- {t}" for t in timeline)}

## Acompanhamento
{chr(10).join(f"- [ ] {a}" for a in rca.get("followUps", [])) or "- [ ] Revisar limites, probes e alertas do workload"}

## Relacionado
Runbooks: {" · ".join(runbooks)} · Time: {" · ".join(f"[[{b}]]" for b in bots)} · [[Incidentes]]
"""
        )
        path = _write_new(root() / INCIDENTS / f"{name}.md", body)
        short = (rca.get("rootCause") or "")[:140].replace("\n", " ")
        line = f"- [[{name}]] ({decision}): {short}"
        _append_to_section(root() / PATTERNS / f"{safe_title(inc.type)}.md", "## Casos", line)
        folder = CLUSTER if kind in NODE_KINDS else SERVICES
        _append_to_section(root() / folder / f"{safe_title(target)}.md", "## Histórico", line)
        if rca.get("learning"):
            learned = " ".join(str(rca["learning"]).split())[:300]
            _append_to_section(
                root() / PATTERNS / f"{safe_title(inc.type)}.md", "## O que aprendemos", f"- {learned} ([[{name}]])"
            )
        return path


def write_lesson(inc: Any, decision: str, reason: str) -> Path | None:
    """Decisão humana (aprovar/rejeitar) com o motivo: o jeito principal de treinar o time."""
    reason = " ".join((reason or "").split())[:600]
    if not reason:
        return None
    ensure_vault()
    with _lock:
        target = inc.deployment or inc.pod
        verb = "aprovou" if decision == "approved" else "rejeitou"
        action = inc.approval.action if inc.approval else "-"
        title = safe_title(f"Licao - {verb} {action} em {target} ({inc.type})", 100)
        path = root() / LESSONS / f"{title}.md"
        n = 2
        while path.exists():
            path = root() / LESSONS / f"{title} {n}.md"
            n += 1
        _write_new(
            path,
            _frontmatter(
                tags=["lição", "decisão-humana"], decisao=decision, acao=action, incidente=inc.id, data=_today()
            )
            + f"""
# {path.stem}

**O operador {verb} `{inc.approval.command if inc.approval else action}`.**

> {reason}

Proposto para: {inc.type} em `{inc.namespace}/{target}`. Causa apontada: {(inc.rca or {}).get("rootCause", "-")}

## Relacionado
[[{inc.type}]] · [[{target}]] · [[Executor]] · [[Lições]]
""",
        )
        _append_to_section(_ensure_pattern(inc.type), "## O que aprendemos", f"- Lição humana: [[{path.stem}]]")
        _append_to_section(
            _ensure_service(inc.namespace, target, getattr(inc, "resourceKind", "Pod") or "Pod"),
            "## Notas",
            f"- [[{path.stem}]]",
        )
        return path


# --------------------------------------------------------------------------- leitura (contexto para os bots)
def _notes() -> list[Path]:
    r = root()
    return [p for p in r.rglob("*.md") if ".obsidian" not in p.parts]


def _section(text: str, header: str) -> str:
    i = text.find(header)
    if i < 0:
        return ""
    j = text.find("\n## ", i + len(header))
    return text[i + len(header) : j if j > 0 else len(text)].strip()


def related(itype: str, target: str, kind: str = "Pod") -> str:
    """O que o time já sabe sobre este padrão e este serviço (vai no prompt do Investigator)."""
    r = root()
    parts: list[str] = []
    pat = r / PATTERNS / f"{safe_title(itype)}.md"
    if pat.exists():
        t = pat.read_text(encoding="utf-8")
        learned = _section(t, "## O que aprendemos")
        cases = _section(t, "## Casos").splitlines()[-3:]
        if learned:
            parts.append(f"Padrão {itype}, o que aprendemos:\n{learned}")
        if cases:
            parts.append(f"Últimos casos de {itype}:\n" + "\n".join(cases))
    svc = r / (CLUSTER if kind in NODE_KINDS else SERVICES) / f"{safe_title(target)}.md"
    if svc.exists():
        t = svc.read_text(encoding="utf-8")
        notes = _section(t, "## Notas")
        hist = _section(t, "## Histórico").splitlines()[-4:]
        if notes:
            parts.append(f"Notas sobre {target}:\n{notes}")
        if hist:
            parts.append(f"Histórico de {target}:\n" + "\n".join(hist))
    for lesson in sorted((r / LESSONS).glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:40]:
        if lesson.stem == "Lições":
            continue
        t = lesson.read_text(encoding="utf-8")
        if f"[[{itype}]]" in t or f"[[{target}]]" in t or "regra" in t.lower()[:400]:
            quote = re.search(r"^> (.+)$", t, re.M)
            parts.append(f"Lição [[{lesson.stem}]]: {quote.group(1) if quote else ''}")
    return "\n\n".join(parts)[:MAX_CONTEXT_CHARS]


def search(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Busca simples por palavras (nome da nota pesa mais). Sem índice: o vault é pequeno."""
    words = [w for w in re.findall(r"[\wáéíóúâêôãõç-]{3,}", (query or "").lower())][:8]
    if not words:
        return []
    scored: list[tuple[float, Path, str]] = []
    for p in _notes():
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        low, name = text.lower(), p.stem.lower()
        score = sum(low.count(w) + 5 * (w in name) for w in words)
        if score:
            first = min((low.find(w) for w in words if w in low), default=0)
            snippet = " ".join(text[max(0, first - 120) : first + 240].split())
            scored.append((score + p.stat().st_mtime / 1e10, p, snippet))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"nota": p.stem, "pasta": p.parent.name, "trecho": s} for _, p, s in scored[:limit]]


def read_note(name: str) -> tuple[str, str]:
    """Lê uma nota pelo nome (como num [[link]]). Devolve (pasta, texto)."""
    stem = safe_title(Path(str(name)).stem.split("|")[0], 120)
    for p in _notes():
        if p.stem == stem:
            return p.parent.name, _inside(p).read_text(encoding="utf-8")[:MAX_NOTE_CHARS]
    raise FileNotFoundError(stem)


# --------------------------------------------------------------------------- escrita pelos bots
def _rate_limit(role: str) -> None:
    now = time.time()
    recent = [t for t in _writes.get(role, []) if now - t < 3600]
    if len(recent) >= NOTES_PER_HOUR:
        raise PermissionError(f"limite de {NOTES_PER_HOUR} notas por hora atingido")
    recent.append(now)
    _writes[role] = recent


def bot_note(role: str, title: str, content: str, links: list[str] | None = None) -> Path:
    ensure_vault()
    name = BOTS.get(role, BOTS["hermes"])[0]
    with _lock:
        _rate_limit(role)
        t = safe_title(title)
        path = _inside(root() / DIARY / name / f"{_today()} - {t}.md")
        clean_links = [safe_title(link, 100) for link in (links or [])][:10]
        rel = " · ".join(f"[[{link}]]" for link in [*clean_links, name])
        body = (
            _frontmatter(tags=["diário", role], autor=role, data=_today(), origem="bot")
            + f"\n# {t}\n\n{str(content)[:MAX_NOTE_CHARS]}\n\n## Relacionado\n{rel}\n"
        )
        if path.exists():
            with path.open("a", encoding="utf-8") as fh:
                fh.write(f"\n---\n{datetime.now():%H:%M}: {str(content)[:MAX_NOTE_CHARS]}\n")
        else:
            _write_new(path, body)
        return path


def runbook_draft(role: str, itype: str, content: str) -> Path:
    """Rascunho de runbook para um padrão novo. Só vira oficial quando você move para 06 - Runbooks."""
    ensure_vault()
    with _lock:
        _rate_limit(role)
        t = safe_title(itype, 60)
        path = _inside(root() / DRAFTS / f"Rascunho - {t}.md")
        _write_new(
            path,
            _frontmatter(
                tags=["runbook", "rascunho"],
                incident_types=[t],
                autor=role,
                data=_today(),
                status="aguardando revisão humana",
            )
            + f"\n# Rascunho de runbook: {t}\n\n> Escrito por um bot. Revise e mova para `{RUNBOOKS}` "
            f"(renomeando para `Runbook - {t}`) para virar oficial.\n\n{str(content)[:MAX_NOTE_CHARS]}\n\n"
            f"## Relacionado\n[[{t}]] · [[Runbooks]]\n",
        )
        _ensure_pattern(t)
        return path


def status() -> dict[str, Any]:
    r = root()
    hubs = {h for _, h, _ in HUBS}
    counts = {
        f: len([p for p in (r / f).glob("*.md") if p.stem not in hubs])
        for f in (SERVICES, PATTERNS, INCIDENTS, LESSONS, RUNBOOKS)
    }
    ok = r.is_dir()
    return {
        "ok": ok,
        "path": str(r),
        "runbooks": counts[RUNBOOKS],
        "detail": (
            f"{counts[INCIDENTS]} incidentes · {counts[PATTERNS]} padrões · {counts[LESSONS]} lições · "
            f"{counts[RUNBOOKS]} runbooks"
        )
        if ok
        else "vault ausente",
    }
