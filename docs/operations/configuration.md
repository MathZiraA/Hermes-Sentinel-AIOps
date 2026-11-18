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

## Operação

| Variável | Padrão | Descrição |
|---|---|---|
| `VERIFY_DELAY_SECONDS` | `90` | Espera antes de conferir se a correção resolveu |
| `VERIFY_ATTEMPTS` / `VERIFY_INTERVAL_SECONDS` | `3` / `30` | Quantas conferências e o intervalo entre elas |
| `ESCALATION_INTERVAL_SECONDS` | `30` | Frequência da checagem de escalonamento |
| `DEPLOY_CORRELATION_MINUTES` | `60` | Janela para ligar um incidente ao último rollout do workload |

## Identidade e acesso

| Variável | Padrão | Descrição |
|---|---|---|
| `AUTH_ENABLED` | `true` | `false` só para demonstração local: todos agem como administrador |
| `SENTINEL_SECRET_KEY` | gerada em `backend/data/secret.key` | Cifra os segredos de 2FA e o estado do SSO. **Defina em produção** (`openssl rand -base64 48`) |
| `SESSION_TTL_HOURS` | `12` | Duração da sessão |
| `COOKIE_SECURE` | `false` | `true` atrás de HTTPS (obrigatório em produção) |
| `SENTINEL_ADMIN_EMAIL` / `SENTINEL_ADMIN_PASSWORD` | — | Cria o primeiro administrador na subida, se não houver usuários. Sem eles, a interface oferece a configuração inicial |
| `OIDC_ISSUER` | — | URL do provedor (ex.: `https://keycloak.empresa.com/realms/ops`). Vazio = SSO desligado |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | — | Credenciais do cliente OIDC |
| `OIDC_REDIRECT_URI` | `http://localhost:8000/api/auth/oidc/callback` | Cadastre a mesma URL no provedor |
| `OIDC_DEFAULT_ROLE` | `viewer` | Papel de quem entra pelo SSO pela primeira vez |
| `OIDC_ALLOWED_DOMAINS` | — | Domínios de e-mail aceitos, separados por vírgula |
| `FRONTEND_URL` | `http://localhost:3000` | Para onde o SSO volta depois do login |

## Integrações

Guia passo a passo em [integrations.md](integrations.md).

| Variável | Descrição |
|---|---|
| `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` | Jira Cloud: um ticket por incidente |
| `JIRA_ISSUE_TYPE` / `JIRA_DONE_TRANSITION` / `JIRA_INCLUDE_SIMULATED` | Tipo da issue (`Task`), transição de fechamento (`Done`), abrir ticket para simulados (`false`) |
| `ZABBIX_WEBHOOK_TOKEN` | Token do webhook `/api/integrations/zabbix` |
| `GRAFANA_URL` / `GRAFANA_DASHBOARD_UID` | Link do painel em cada incidente |
| `LOKI_URL` / `LOKI_TOKEN` / `LOKI_SELECTOR` | Logs centralizados no incidente e na ferramenta MCP `buscar_logs_loki` |
| `GITHUB_DEPLOY_REPOS` | `workload=org/repo,…`: commits do deploy correlacionado |

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
