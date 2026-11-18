"""Consumo de IA: orçamento diário (com corte) e custo estimado."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from config import settings
from db import engine as db
from db.models import AiUsage


def today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


async def _row(s: Any, provider: str) -> AiUsage:
    row = await s.get(AiUsage, (today(), provider))
    if row is None:
        row = AiUsage(day=today(), provider=provider, calls=0, blocked=0, tokens_in=0, tokens_out=0)
        s.add(row)
    return row


async def totals_today() -> dict[str, int]:
    async with db.session() as s:
        rows = (await s.scalars(select(AiUsage).where(AiUsage.day == today()))).all()
    return {
        "calls": sum(r.calls for r in rows),
        "tokens": sum(r.tokens_in + r.tokens_out for r in rows),
        "blocked": sum(r.blocked for r in rows),
    }


async def budget_left() -> tuple[bool, str]:
    """(pode chamar?, motivo). Limite 0 = sem limite."""
    t = await totals_today()
    if settings.ai_daily_call_limit and t["calls"] >= settings.ai_daily_call_limit:
        return False, f"orçamento diário de {settings.ai_daily_call_limit} chamadas atingido"
    if settings.ai_daily_token_limit and t["tokens"] >= settings.ai_daily_token_limit:
        return False, f"orçamento diário de {settings.ai_daily_token_limit} tokens atingido"
    return True, ""


async def record(provider: str, tokens_in: int = 0, tokens_out: int = 0, blocked: bool = False) -> None:
    async with db.session() as s:
        row = await _row(s, provider)
        if blocked:
            row.blocked += 1
        else:
            row.calls += 1
            row.tokens_in += int(tokens_in or 0)
            row.tokens_out += int(tokens_out or 0)
        await s.commit()


def _cost(tokens_in: int, tokens_out: int) -> float:
    return round(
        tokens_in / 1000 * settings.ai_cost_input_per_1k + tokens_out / 1000 * settings.ai_cost_output_per_1k, 4
    )


async def usage(days: int = 30) -> dict[str, Any]:
    since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    async with db.session() as s:
        rows = (await s.scalars(select(AiUsage).where(AiUsage.day >= since).order_by(AiUsage.day))).all()
    by_day: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = by_day.setdefault(r.day, {"day": r.day, "calls": 0, "blocked": 0, "tokensIn": 0, "tokensOut": 0})
        d["calls"] += r.calls
        d["blocked"] += r.blocked
        d["tokensIn"] += r.tokens_in
        d["tokensOut"] += r.tokens_out
    for d in by_day.values():
        d["cost"] = _cost(d["tokensIn"], d["tokensOut"])
    t = await totals_today()
    return {
        "provider": settings.ai_provider,
        "model": settings.ai_model or (settings.hermes_model if settings.ai_provider == "hermes" else ""),
        "limits": {"callsPerDay": settings.ai_daily_call_limit, "tokensPerDay": settings.ai_daily_token_limit},
        "today": t,
        "days": list(by_day.values()),
        "totalCost": round(sum(d["cost"] for d in by_day.values()), 4),
    }
