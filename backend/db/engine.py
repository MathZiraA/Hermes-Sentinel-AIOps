"""Conexão com o banco (assíncrona) e migrações na subida."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from config import settings

log = logging.getLogger("sentinel.db")

_engine: AsyncEngine | None = None
_sessions: async_sessionmaker[AsyncSession] | None = None


def database_url() -> str:
    return settings.database_url


def engine() -> AsyncEngine:
    global _engine, _sessions
    if _engine is None:
        url = database_url()
        if url.startswith("sqlite"):
            path = url.split("///", 1)[-1]
            if path and path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(url, pool_pre_ping=not url.startswith("sqlite"))
        _sessions = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def configure(url: str) -> None:
    """Troca o banco (usado pelos testes)."""
    global _engine, _sessions
    _engine = create_async_engine(url)
    _sessions = async_sessionmaker(_engine, expire_on_commit=False)


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    engine()
    assert _sessions is not None  # noqa: S101 (inicializado por engine())
    async with _sessions() as s:
        yield s


def _alembic(url: str, action: str, target: str) -> None:
    from alembic import command
    from alembic.config import Config

    here = Path(__file__).resolve().parent.parent
    cfg = Config(str(here / "alembic.ini"))
    cfg.set_main_option("script_location", str(here / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    logging.getLogger("alembic").setLevel(logging.WARNING)  # o log do backend não precisa do detalhe
    getattr(command, action)(cfg, target)


async def downgrade_all() -> None:
    """Desfaz todas as migrações (usado pelos testes contra PostgreSQL)."""
    await asyncio.to_thread(_alembic, database_url(), "downgrade", "base")


async def migrate() -> None:
    """Aplica as migrações pendentes (alembic upgrade head)."""
    url = database_url()
    if url.startswith("sqlite"):
        path = url.split("///", 1)[-1]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(_alembic, url, "upgrade", "head")
    log.info("banco pronto (%s)", url.split("://", 1)[0])
