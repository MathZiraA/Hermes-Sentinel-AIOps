# Interface web

Frontend em React + TanStack Start, criado no [Lovable](https://lovable.dev). Os arquivos de configuração
(`package.json`, `vite.config.ts`, `tsconfig.json`…) ficam na raiz do repositório porque o Lovable exige.

| Pasta / arquivo   | O que tem                                                                  |
| ----------------- | -------------------------------------------------------------------------- |
| `routes/`         | páginas (roteamento por arquivo, ver [`routes/README.md`](routes/README.md)) |
| `components/`     | componentes por área: `incidents/`, `brain/`, `office/` (escritório 3D), `layout/`… |
| `components/ui/`  | componentes base do shadcn/ui                                              |
| `lib/api/`        | cliente da API do backend                                                  |
| `lib/auth/`       | sessão do usuário e login                                                  |
| `lib/i18n/`       | traduções (português e inglês)                                             |
| `lib/theme/`      | tema claro e escuro                                                        |
| `lib/storage/`    | preferências salvas no navegador                                           |
| `lib/sentinel/`   | estado dos incidentes e dos agentes em tempo real                          |
| `hooks/`          | hooks React compartilhados                                                 |
| `assets/`         | imagens importadas pelo código                                             |
| `test/`           | testes Vitest                                                              |
| `routeTree.gen.ts`| **gerado automaticamente**: não editar                                     |

## Comandos

```bash
make dev        # interface em :3000 (junto com a API)
make test-web   # vitest
make lint-web   # ESLint + Prettier
make typecheck  # TypeScript
```

A imagem Docker fica em [`deploy/docker/web.Dockerfile`](../deploy/docker/web.Dockerfile).
