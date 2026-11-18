import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
async def database(tmp_path, monkeypatch):
    """Banco novo por teste, criado pelas migrações reais (testa o Alembic junto).

    Padrão: SQLite em arquivo temporário. Com TEST_DATABASE_URL (CI), usa PostgreSQL e desfaz tudo no fim.
    """
    from db import engine as db

    pg_url = os.getenv("TEST_DATABASE_URL")
    url = pg_url or f"sqlite+aiosqlite:///{tmp_path / 'sentinel.db'}"
    monkeypatch.setattr(db, "database_url", lambda: url)
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_sessions", None)
    await db.migrate()
    yield url
    if db._engine is not None:
        await db._engine.dispose()
    if pg_url:
        await db.downgrade_all()
