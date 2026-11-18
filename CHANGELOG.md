# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

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

### Segurança

- Logs e eventos tratados como dados não confiáveis, com redação de segredos antes de qualquer envio.
- Detecção de OOM por `exit 137` com limite de memória, quando o kernel mata um processo filho.
- Ação desconhecida sugerida pela IA vira `none`: o sistema nunca chuta uma correção.
- Testes de persistência rodam também contra PostgreSQL 17 no CI.

[Não lançado]: https://github.com/MathZiraA/Hermes-Sentinel-AIOps/commits/main
