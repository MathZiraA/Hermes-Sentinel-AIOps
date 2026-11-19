# Deploy

Tudo o que é preciso para rodar o Hermes Sentinel fora do modo de desenvolvimento.

| Pasta                  | O que tem                                                                 |
| ---------------------- | ------------------------------------------------------------------------- |
| `docker/`              | Dockerfiles das duas imagens: `backend.Dockerfile` e `web.Dockerfile`     |
| `compose/`             | Docker Compose com PostgreSQL e Caddy na frente (um servidor só)          |
| `helm/hermes-sentinel` | Helm chart para instalar no Kubernetes                                    |

As duas imagens são construídas a partir da **raiz do repositório**:

```bash
docker build -f deploy/docker/backend.Dockerfile -t hermes-sentinel/backend .
docker build -f deploy/docker/web.Dockerfile -t hermes-sentinel/web .
```

As versões publicadas ficam no GHCR (`ghcr.io/mathziraa/hermes-sentinel-backend` e `-web`), geradas pelo
workflow de release a cada tag `vX.Y.Z`.

Guias passo a passo:

- [Docker Compose](../docs/operations/deploy-compose.md)
- [Helm](../docs/operations/deploy-helm.md)
- [Configuração](../docs/operations/configuration.md)
