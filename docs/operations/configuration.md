# Configuração

Toda a configuração vem de variáveis de ambiente, lidas do `.env` na raiz do projeto. O `.env` nunca vai para o Git;
o [`.env.example`](../../.env.example) lista tudo sem valores.

## Hermes (IA)

| Variável | Padrão | Descrição |
|---|---|---|
| `HERMES_GATEWAY_URL` | `https://hermes.example.internal:8443` | API OpenAI-compatível do Hermes Agent |
| `HERMES_GATEWAY_TOKEN` | — | Token estático do gateway (`API_SERVER_KEY` do servidor). Vazio = sem IA, só runbooks |
| `HERMES_MODEL` | `hermes-agent` | Nome do modelo exposto pelo gateway |
| `HERMES_MODE` | `gateway` | `gateway` (HTTP) ou `cli` (chama `hermes chat` local) |
| `HERMES_LOCAL_CLI_PATH` | `~/.hermes` | Instalação local do Hermes, para `HERMES_MODE=cli` |
| `HERMES_TIMEOUT_SECONDS` | `90` | Tempo máximo de uma chamada simples |
| `HERMES_AGENT_TIMEOUT_SECONDS` | `240` | Tempo máximo da investigação agêntica (várias ferramentas) |
| `AI_MIN_INTERVAL_SECONDS` | `8` | Intervalo mínimo entre chamadas de IA (protege a cota) |
| `GEMINI_API_KEY` | — | Opcional: chamada direta ao Gemini quando o gateway responde 429/ocupado |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.5-flash-lite` | Modelo do fallback direto |
| `SSL_CERT_FILE` | bundle do sistema | CA usada para validar o HTTPS do gateway |

## Kubernetes

| Variável | Padrão | Descrição |
|---|---|---|
| `KUBECONFIG_PATH` | `~/.kube/config` | Kubeconfig usado pelo Monitor e pelo Executor |
| `K8S_NAMESPACES` | — | Lista separada por vírgula; também limita o que o MCP enxerga. Vazio: o Monitor vigia todos os namespaces que não são de sistema, e o MCP libera só `stockflow`. Recomendado: defina sempre |
| `K8S_LOG_TAIL_LINES` | `80` | Máximo de linhas de log por leitura |

## Servidor MCP

| Variável | Padrão | Descrição |
|---|---|---|
| `SENTINEL_MCP_TOKEN` | — | Token principal (Hermes padrão e fluxo automático). Vazio = MCP desligado |
| `SENTINEL_MCP_ROLE_TOKENS` | — | Um token por bot: `monitor:tok,supervisor:tok,investigator:tok,executor:tok,itsm:tok` |
| `SENTINEL_MCP_PORT` | `8765` | Porta local (sempre em `127.0.0.1`) |

Gere tokens com `openssl rand -hex 32`. Permissões de cada papel: [docs/api](../api/README.md#servidor-mcp).

## Banco de dados e SLA

| Variável | Padrão | Descrição |
|---|---|---|
| `DATABASE_URL` | SQLite em `backend/data/sentinel.db` | Produção: `postgresql+asyncpg://usuario:senha@host:5432/sentinel` |
| `AUTO_MIGRATE` | `true` | Aplica as migrações ao subir. Desligue se o time de banco aplica com `alembic upgrade head` |
| `SLA_ACK_MINUTES` | `5,15,60,1440` | Minutos para reconhecer SEV1, SEV2, SEV3 e SEV4 |
| `SLA_RESOLVE_MINUTES` | `60,240,1440,4320` | Minutos para resolver SEV1, SEV2, SEV3 e SEV4 |
| `SENTINEL_CLUSTER_ID` | `local` | Identificador deste cluster no Sentinel |
| `SENTINEL_CLUSTER_NAME` | contexto do kubeconfig | Nome exibido |

## Memória e integrações

| Variável | Padrão | Descrição |
|---|---|---|
| `OBSIDIAN_VAULT_PATH` | `./obsidian-vault` | Pasta do Hermes Brain |
| `GITHUB_TOKEN` | — | Opcional: o ITSM abre uma issue por incidente |
| `GITHUB_REPO` | `MathZiraA/Hermes-Sentinel-AIOps` | Repositório das issues |

## Servidor local

| Variável | Padrão | Descrição |
|---|---|---|
| `BACKEND_PORT` | `8000` | Porta da API |
| `FRONTEND_PORT` | `3000` | Porta da interface |
| `CORS_ORIGINS` | localhost nas portas 3000/5173/8080 | Origens aceitas pela API |

## Rotação de tokens

1. Gere o novo valor (`openssl rand -hex 32`).
2. Atualize o `.env` do Sentinel e o `.env` correspondente no Hermes (`/opt/hermes/data/.env` para o token principal,
   `profiles/<bot>/.env` para os tokens de bot).
3. Reinicie o backend (`make dev`) e o container do Hermes.
