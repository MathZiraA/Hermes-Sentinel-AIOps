"""Índice do Hermes Brain no banco: busca BM25 sem acento e, opcionalmente, semântica (embeddings).

O Obsidian continua sendo onde as pessoas editam; este índice é sincronizado a cada minuto (por data de
modificação) e é o que os bots e a interface consultam. Sem banco, cai para a busca em arquivo do brain.py.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import unicodedata
from collections import Counter
from typing import Any

import httpx
from sqlalchemy import delete, select

from config import settings
from db import engine as db
from db.models import BrainNote, utcnow
from integrations import brain

log = logging.getLogger("sentinel.brain.index")
SYNC_SECONDS = 60
K1, B = 1.4, 0.75
_STOP = set(
    [
        "a",
        "o",
        "os",
        "as",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "um",
        "uma",
        "para",
        "por",
        "com",
        "que",
        "se",
        "ao",
        "à",
        "é",
    ]
)


def tokens(text: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return [t for t in re.findall(r"[a-z0-9][a-z0-9-]{1,}", plain) if t not in _STOP]


# --------------------------------------------------------------------------- embeddings (opcional)
async def embed(texts: list[str]) -> list[list[float]] | None:
    if not settings.ai_embeddings:
        return None
    try:
        if settings.ai_provider == "openai" and settings.ai_base_url:
            headers = {"Authorization": f"Bearer {settings.ai_api_key}"} if settings.ai_api_key else {}
            async with httpx.AsyncClient(timeout=30) as http:
                r = await http.post(
                    f"{settings.ai_base_url}/embeddings",
                    headers=headers,
                    json={"model": settings.ai_embedding_model, "input": texts},
                )
            r.raise_for_status()
            return [d["embedding"] for d in r.json()["data"]]
        if settings.gemini_api_key:
            from google import genai

            client = genai.Client(api_key=settings.gemini_api_key)
            resp = await client.aio.models.embed_content(model=settings.ai_embedding_model, contents=texts)
            return [list(e.values) for e in resp.embeddings]
    except Exception as exc:
        log.warning("embeddings indisponíveis (%s): seguindo só com BM25", type(exc).__name__)
    return None


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# --------------------------------------------------------------------------- sincronização
async def sync() -> dict[str, int]:
    """Traz para o banco as notas novas/alteradas e remove as apagadas."""
    files = await asyncio.to_thread(brain._notes)
    on_disk = {}
    for p in files:
        try:
            on_disk[p.stem] = (p, p.stat().st_mtime)
        except OSError:
            continue
    async with db.session() as s:
        rows = {r.name: r for r in (await s.scalars(select(BrainNote))).all()}
        changed = [(name, p, m) for name, (p, m) in on_disk.items() if name not in rows or rows[name].mtime < m]
        texts = [p.read_text(encoding="utf-8", errors="replace")[:20000] for _, p, _ in changed]
        vectors = await embed([t[:4000] for t in texts]) if changed else None
        for i, (name, p, m) in enumerate(changed):
            folder = p.relative_to(brain.root()).parts[0] if p.parent != brain.root() else ""
            row = rows.get(name) or BrainNote(name=name)
            row.folder, row.text, row.mtime, row.indexed_at = folder, texts[i], m, utcnow()
            row.embedding = vectors[i] if vectors else row.embedding if name in rows else None
            s.add(row)
        gone = [n for n in rows if n not in on_disk]
        if gone:
            await s.execute(delete(BrainNote).where(BrainNote.name.in_(gone)))
        await s.commit()
    return {"indexed": len(changed), "removed": len(gone), "total": len(on_disk)}


async def sync_loop() -> None:
    while True:
        try:
            await sync()
        except Exception as exc:
            log.debug("sincronização do índice falhou: %s", type(exc).__name__)
        await asyncio.sleep(SYNC_SECONDS)


# --------------------------------------------------------------------------- busca
def _snippet(text: str, terms: list[str]) -> str:
    low = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    pos = min((low.find(t) for t in terms if t in low), default=0)
    return " ".join(text[max(0, pos - 120) : pos + 240].split())


async def search(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """BM25 (título pesa o dobro) + similaridade de embedding quando disponível. Cai para a busca em arquivo."""
    terms = tokens(query)[:12]
    if not terms:
        return []
    try:
        async with db.session() as s:
            rows = (await s.scalars(select(BrainNote))).all()
    except Exception:
        rows = []
    if not rows:
        return await asyncio.to_thread(brain.search, query, limit)
    docs = [(r, Counter(tokens(r.text) + tokens(r.name) * 2)) for r in rows]
    n = len(docs)
    avg = sum(sum(c.values()) for _, c in docs) / n or 1
    df = Counter(t for _, c in docs for t in set(c) if t in terms)
    scores: list[tuple[float, Any]] = []
    qvec = None
    if settings.ai_embeddings and any(r.embedding for r in rows):
        vecs = await embed([query])
        qvec = vecs[0] if vecs else None
    for r, c in docs:
        length = sum(c.values()) or 1
        bm25 = sum(
            math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) * c[t] * (K1 + 1) / (c[t] + K1 * (1 - B + B * length / avg))
            for t in terms
            if c[t]
        )
        score = bm25
        if qvec and r.embedding:
            score = bm25 / (1 + bm25) + cosine(qvec, r.embedding)  # híbrido: as duas escalas em [0, ~1]
        if score > 0:
            scores.append((score, r))
    scores.sort(key=lambda x: x[0], reverse=True)
    return [
        {"nota": r.name, "pasta": r.folder, "trecho": _snippet(r.text, terms), "score": round(sc, 3)}
        for sc, r in scores[:limit]
    ]
