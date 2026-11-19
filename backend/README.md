# Backend

API FastAPI, Monitor do cluster, orquestrador dos agentes, servidor MCP e Hermes Brain. Python 3.12+.

| Pasta / arquivo   | O que tem                                                              |
| ----------------- | ---------------------------------------------------------------------- |
| `main.py`         | aplicação FastAPI: monta as rotas e sobe o Monitor                     |
| `config.py`       | todas as configurações (lidas do `.env`), ver `docs/operations/configuration.md` |
| `mcp_server.py`   | servidor MCP que o Hermes usa para falar com o Sentinel                |
| `api/`            | rotas REST por área (incidentes, admin, operações, integrações…)       |
| `agents/`         | orquestração dos cinco agentes                                         |
| `agent/`          | agente de cluster remoto (`python -m agent`), para o multicluster      |
| `core/`           | barramento de eventos e telemetria                                     |
| `db/`             | modelos SQLAlchemy e repositórios                                      |
| `migrations/`     | migrações Alembic (`alembic.ini` aponta para cá)                       |
| `domain/`         | regras puras: ciclo de vida, SLA, ações, permissões                    |
| `identity/`       | login, sessões, 2FA, OIDC, limite de tentativas                        |
| `integrations/`   | Hermes, Hermes Brain, Obsidian, GitHub, Jira, notificações, observabilidade |
| `k8s/`            | cliente Kubernetes, Monitor (watch + varredura) e autorremediação      |
| `schemas/`        | contratos de eventos e incidentes                                      |
| `scripts/`        | utilitários (exportar o OpenAPI para `docs/api/`)                      |
| `tests/`          | testes pytest                                                          |

## Comandos

Rodados da raiz do repositório:

```bash
make setup          # cria backend/.venv e instala as dependências
make dev            # sobe a API em :8000 (junto com a interface)
make test-backend   # pytest
make lint-backend   # ruff
make openapi        # atualiza docs/api/openapi.json
```

A imagem Docker fica em [`deploy/docker/backend.Dockerfile`](../deploy/docker/backend.Dockerfile).
