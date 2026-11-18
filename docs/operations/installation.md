# Instalação (desenvolvimento e demonstração)

> Em `0.1.x` o Sentinel roda direto na máquina. Helm chart e Docker Compose chegam na Fase 7 ([ROADMAP](../../ROADMAP.md)).

## Requisitos

| Item | Versão | Para quê |
|---|---|---|
| Linux (testado no Fedora 44) | — | scripts de instalação |
| Python | 3.12+ | backend |
| Node.js ou Bun | Node 20+ | frontend |
| `make` | — | atalhos |
| `kubectl` + `kind` + Podman | opcional | cluster local de teste |
| Hermes Agent | opcional | investigação por IA (sem ele, o diagnóstico usa os runbooks) |

## Passo a passo

```bash
git clone https://github.com/MathZiraA/Hermes-Sentinel-AIOps.git
cd Hermes-Sentinel-AIOps
make setup            # ou: make setup-kind (instala kubectl + kind)
```

O `make setup` é seguro para rodar de novo. Ele:

1. confere Python, pip, Node/Bun e kubectl;
2. cria `backend/.venv` e instala `backend/requirements-dev.txt`;
3. instala as dependências do frontend;
4. cria o `.env` a partir do `.env.example` (permissão `600`) e a pasta do Hermes Brain.

Preencha o `.env` (referência completa em [configuration.md](configuration.md)) e suba:

```bash
make dev
```

| Endereço | O quê |
|---|---|
| http://localhost:3000 | interface |
| http://localhost:8000/docs | API (Swagger) |
| ws://localhost:8000/ws/telemetry | telemetria em tempo real |

## Cluster de teste (opcional)

```bash
kind create cluster --name stockflow
kubectl create namespace stockflow
```

Com `K8S_NAMESPACES=stockflow` no `.env`, o Monitor passa a vigiar o namespace. Sem cluster, a interface funciona no
modo simulação (botão **Simular Incidente**).

## Conferir a instalação

```bash
make check                                   # lint, tipos e testes
curl -s localhost:8000/api/health | jq .     # kubernetes, hermesGateway, obsidian, mcp
```

## Abrir o Hermes Brain no Obsidian

No Obsidian, use **Abrir outro vault → Abrir pasta como vault** e escolha a pasta de `OBSIDIAN_VAULT_PATH`
(padrão: `obsidian-vault/`). A visão de grafo (Ctrl+G) mostra cada pasta numa cor.

Próximo passo: ligar o Hermes ao cluster, em [demo-environment.md](demo-environment.md).
