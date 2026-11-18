# Contribuindo com o Hermes Sentinel

Obrigado pelo interesse! Este guia explica como o repositório é organizado e o que um PR precisa ter para ser aceito.

## Sumário

- [Ambiente de desenvolvimento](#ambiente-de-desenvolvimento)
- [Fluxo de branches](#fluxo-de-branches)
- [Commits](#commits)
- [Pull requests](#pull-requests)
- [Padrões de código](#padrões-de-código)
- [Decisões de arquitetura (ADRs)](#decisões-de-arquitetura-adrs)
- [Frontend e Lovable](#frontend-e-lovable)

## Ambiente de desenvolvimento

Requisitos: Python 3.12+, Node 20+ (ou Bun), `make`. Para testar contra um cluster real, `kubectl` e `kind`.

```bash
make setup        # venv do backend, dependências do frontend e .env
make dev          # backend :8000 + frontend :3000
make check        # lint + tipos + testes (o mesmo que o CI roda)
```

O guia completo está em [docs/operations/installation.md](docs/operations/installation.md).

Opcional, mas recomendado: ganchos de pre-commit, que rodam ruff, Prettier e a busca de segredos antes de cada commit.

```bash
pipx install pre-commit && pre-commit install
```

## Fluxo de branches

- `main` está **sempre funcionando**: é sincronizada com o editor do Lovable e é a base das releases.
- Todo trabalho acontece numa branch curta, criada a partir da `main`:

| Prefixo | Uso |
|---|---|
| `feat/` | funcionalidade nova |
| `fix/` | correção de bug |
| `docs/` | só documentação |
| `refactor/` | mudança interna sem alterar comportamento |
| `chore/` | manutenção, dependências, ferramentas |
| `ci/` | pipelines |

- Nada vai para a `main` sem PR. Nunca reescreva o histórico da `main` (force push, rebase de commits já publicados).

## Commits

Seguimos [Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/). O título do PR também segue o padrão, porque ele vira o commit de merge.

```
<tipo>(<escopo opcional>): <resumo no imperativo, minúsculo, sem ponto final>

<corpo opcional: o porquê da mudança>

<rodapé opcional: BREAKING CHANGE: …, Refs #123>
```

Tipos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
Escopos comuns: `backend`, `web`, `watcher`, `mcp`, `brain`, `hermes`, `api`, `deps`, `repo`.

Exemplos:

```
feat(watcher): detectar PVC preso em Pending
fix(mcp): devolver ToolError quando o pod já foi recriado
docs(adr): registrar decisão sobre tokens por bot
```

As versões seguem [SemVer](https://semver.org/lang/pt-BR/) e o [CHANGELOG](CHANGELOG.md) segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## Pull requests

Um PR é aceito quando:

1. o CI está verde (lint, tipos, testes, auditoria de dependências, busca de segredos, build);
2. o template de PR está preenchido: o que muda, por quê e como foi testado;
3. comportamento novo tem teste;
4. a documentação acompanha a mudança (README, `docs/`, CHANGELOG em `[Não lançado]`);
5. decisões de arquitetura relevantes têm um ADR novo.

PRs pequenos e focados são revisados mais rápido. Use rascunho (draft) para pedir opinião cedo.

## Padrões de código

**Backend (Python):**
- `ruff` é a fonte da verdade para lint e formatação (`make lint-backend`, `make format`).
- Toda chamada à API do Kubernetes é síncrona e roda em `asyncio.to_thread`.
- Nada altera o cluster sem passar pelo fluxo de aprovação do Executor.
- Texto vindo do cluster (logs, eventos) é **dado não confiável**: passe por `redact()` e marque como tal antes de mandar para a IA.

**Frontend (TypeScript/React):**
- ESLint + Prettier (`make lint-web`) e `tsc --noEmit` sem erros.
- A cena isométrica é CSS 3D puro (`src/components/office/iso.tsx`). Nunca coloque um elemento sem `preserve-3d` entre o mundo e os objetos.

**Segredos:** nunca entram no Git. Use `.env` (ignorado) e documente a variável em `.env.example`, sem valor.

## Decisões de arquitetura (ADRs)

Decisões que mudam a arquitetura, a segurança ou um contrato público ganham um ADR em
[`docs/architecture/adr/`](docs/architecture/adr/). Copie o [modelo](docs/architecture/adr/0000-modelo.md), use o próximo número e
inclua o ADR no mesmo PR da mudança.

## Frontend e Lovable

O frontend nasceu no [Lovable](https://lovable.dev) e continua conectado a ele. O que entra na `main` aparece no editor do Lovable,
então a `main` precisa sempre compilar. Não edite arquivos gerados (como `src/routeTree.gen.ts`) e siga as regras de
[AGENTS.md](AGENTS.md).
