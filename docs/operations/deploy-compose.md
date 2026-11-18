# Instalação com Docker Compose (uma VM)

Para avaliação, times pequenos ou um servidor dedicado. Sobe PostgreSQL, backend, interface e um proxy Caddy que
publica tudo numa origem só.

```bash
cp deploy/compose/.env.example deploy/compose/.env
# preencha POSTGRES_PASSWORD (openssl rand -hex 24), SENTINEL_SECRET_KEY (openssl rand -base64 48),
# PUBLIC_URL, K8S_NAMESPACES e o provedor de IA
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env up -d --build
```

Abra `PUBLIC_URL` (padrão http://localhost:8080) e crie o administrador na tela de configuração inicial.

| Serviço | Imagem | Papel |
|---|---|---|
| `postgres` | `postgres:17-alpine` | Banco (volume `pgdata`) |
| `backend` | `hermes-sentinel/backend` | API, Monitor, MCP e Hermes Brain (volume `brain`); lê o kubeconfig montado em modo leitura |
| `web` | `hermes-sentinel/web` | Interface (Node, sem root) |
| `proxy` | `caddy:2-alpine` | `/api` e `/ws` → backend, o resto → interface; `/metrics` não é publicado |

**HTTPS:** troque `:80` no [Caddyfile](../../deploy/compose/Caddyfile) pelo domínio (ex.: `sentinel.empresa.com`),
publique as portas 80/443 e defina `COOKIE_SECURE=true` e `PUBLIC_URL=https://…`. O Caddy obtém o certificado sozinho.

**Atualizar:** `git pull && docker compose … up -d --build`. As migrações do banco rodam na subida.

**Backup:** `docker compose exec postgres pg_dump -U sentinel sentinel > backup.sql` e o volume `brain`.
