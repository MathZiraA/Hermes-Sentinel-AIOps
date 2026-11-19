# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Alterado

- Dockerfiles movidos para `deploy/docker/` (`backend.Dockerfile` e `web.Dockerfile`); CI, release e Compose
  atualizados.

### Documentação

- README em cada pasta principal (`backend/`, `src/`, `deploy/`, `scripts/`) e árvore do repositório atualizada.

## [1.0.0] - 2026-11-18

Primeira versão estável: de demonstração a produto self-hosted.

### Adicionado

- **Multicluster** por agente de saída (`python -m agent`): token por cluster, sinais enriquecidos e execução só de
  correções aprovadas na central, com verificação.
- **Distribuição**: imagens Docker sem root, Docker Compose com PostgreSQL e Caddy, Helm chart com RBAC de menor
  privilégio, Ingress e ServiceMonitor; workflow de release (imagens no GHCR + chart).
- **Observabilidade**: métricas Prometheus (`/metrics`), logs JSON e probes de liveness e readiness.

- **Backend FastAPI** com WebSocket de telemetria (`/ws/telemetry`), simulação de incidentes, aprovação e rejeição.
- **Monitor determinístico e abrangente**: watch de Pods mais varredura periódica de nós, deployments, statefulsets,
  jobs, PVCs, HPAs, eventos Warning e memória perto do limite. Motivos desconhecidos viram incidente com o próprio nome.
- **Correlação de sinais**: vários sinais do mesmo workload formam um único incidente.
- **Investigação agêntica**: o Hermes (no VPS) investiga pelo servidor MCP do Sentinel, com fallback para diagnóstico
  com logs no prompt e, por último, para o runbook local.
- **Servidor MCP `sentinel`** com 15 ferramentas: leitura do cluster e da memória, mais três de escrita controlada
  (`memoria_registrar`, `runbook_rascunho` e `propor_correcao`, que só cria um pedido de aprovação). Autenticação
  Bearer e **um token por bot**, com permissões por papel (`ROLE_TOOLS`).
- **Hermes Brain**: vault Obsidian com Serviços, Padrões, Incidentes, Lições, Runbooks e Diário dos bots, ligados por
  wikilinks. As decisões humanas (com motivo) viram Lições que entram no contexto das próximas investigações.
- **Aprovação humana** antes de qualquer alteração no cluster, com motivo opcional (`{"motivo": "…"}`).
- **Interface isométrica** com os cinco agentes, Kanban, banner de aprovação e painel de conexões.
- Scripts de instalação (Fedora) e de desenvolvimento, `Makefile` e exportação do contrato OpenAPI.

- **Persistência** em PostgreSQL (SQLite na demo) com migrações Alembic aplicadas na subida.
- **Ciclo de vida do incidente** validado (detectado → reconhecido → investigando → aguardando aprovação → corrigindo
  → monitorando → resolvido → post-mortem, mais encerrado e falhou) e linha do tempo persistida.
- **SEV1–SEV4 com SLA** configurável de reconhecimento e resolução; `POST /api/incidents/{id}/acknowledge`.
- **Auditoria imutável**: cadeia SHA-256, triggers que recusam alteração, verificação e exportação JSON/CSV.
- **Relatórios** com MTTA, MTTR e volume por severidade, status, serviço e tipo; lista de clusters.
- **Retomada após reinício**: pedidos de aprovação sobrevivem; investigações interrompidas recomeçam.
- **Separação de deveres**: quem propõe uma correção não decide sobre ela.

- **Login** com sessão HttpOnly revogável, primeira configuração do administrador e troca de senha.
- **Papéis** Admin, Operador, Visualizador e Auditor, com **times e escopo** por cluster e namespace.
- **2FA** (TOTP) opcional com segredo cifrado, e **SSO OIDC** (Authorization Code + PKCE).
- Administração de usuários e times; tela de login com 2FA e SSO; botões de decisão conforme o papel.
- Motivo obrigatório para rejeitar uma correção (na tela e na API).

- **Interface profissional**: painel com navegação por papel, Visão geral, Incidentes com filtros, detalhe do
  incidente com decisão e linha do tempo, Clusters, Hermes Brain com grafo interativo, Relatórios, Auditoria,
  Usuários, Times e Minha conta. O escritório isométrico virou a Sala de guerra.
- Tema escuro (padrão) e claro, interface em português e inglês, layout responsivo para aprovar pelo celular.
- API para as telas: estado do cluster (`/api/clusters/{id}/status`) e Hermes Brain (`/api/brain/graph`,
  `/api/brain/search`, `/api/brain/notes/{nome}`).

- **Ações novas** com parâmetros validados e comando equivalente: voltar revisão, ajustar limites de CPU/memória,
  isolar/drenar nó e reexecutar job.
- **Verificação pós-correção**: o incidente fica em monitoramento e reabre (uma vez) se a correção não resolveu.
- **Janelas de manutenção** (silêncios), **autorremediação** de baixo risco por política com limite por hora, e
  **plantão** com escalonamento primário → secundário → administradores.
- **Correlação com deploys**: incidentes logo após um rollout mostram a revisão e a troca de imagem.
- Tela **Manutenção e plantão** e, no incidente, responsáveis, escalonamento, deploy recente e reaberturas.

- **Jira**: um ticket por incidente, com prioridade pela severidade, atribuição ao plantão com menção, comentários
  em cada etapa e fechamento automático.
- **Zabbix**: webhook autenticado que transforma alertas em incidentes, com deduplicação e recuperação.
- **Grafana** (link do painel no intervalo do incidente), **Loki** (logs centralizados no incidente e ferramenta MCP
  `buscar_logs_loki`) e **GitHub** (commits do deploy correlacionado).
- Links externos no detalhe do incidente e estado das integrações na tela de Clusters.

- **Provedor de IA trocável**: Hermes (agente com MCP), qualquer API compatível com OpenAI (OpenAI, Claude, Ollama,
  vLLM) ou Gemini direto.
- **Orçamento diário** de chamadas e tokens com corte automático, consumo por dia e custo estimado nos Relatórios.
- **Avaliação humana do diagnóstico** (certo/errado), com lição automática e taxa de acerto por fonte.
- **Memória indexada no banco**, sincronizada com o Obsidian, com busca BM25 sem acento e busca semântica opcional.

### Segurança

- Logs e eventos tratados como dados não confiáveis, com redação de segredos antes de qualquer envio.
- Detecção de OOM por `exit 137` com limite de memória, quando o kernel mata um processo filho.
- Ação desconhecida sugerida pela IA vira `none`: o sistema nunca chuta uma correção.
- Testes de persistência rodam também contra PostgreSQL 17 no CI.
- Senhas com argon2id, bloqueio após 5 falhas de login, falhas auditadas e recusa de escritas de outras origens (CSRF).
- O último administrador não pode ser rebaixado nem desativado; mudanças de acesso derrubam as sessões.
- O leitor de notas do Hermes Brain nunca interpreta HTML (sem XSS).

[Não lançado]: https://github.com/MathZiraA/Hermes-Sentinel-AIOps/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/MathZiraA/Hermes-Sentinel-AIOps/releases/tag/v1.0.0
