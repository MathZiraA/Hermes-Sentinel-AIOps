"""Exporta o contrato OpenAPI do backend (usado em docs/api e verificado no CI).

cd backend && .venv/bin/python -m scripts.export_openapi ../docs/api/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(out: str) -> None:
    from main import app  # import tardio: só carrega o app quando o script roda

    spec = app.openapi()
    Path(out).write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI {spec['info']['version']}: {len(spec['paths'])} rotas → {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
