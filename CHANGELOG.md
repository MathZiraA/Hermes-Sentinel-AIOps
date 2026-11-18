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

### Segurança

- Logs e eventos tratados como dados não confiáveis, com redação de segredos antes de qualquer envio.
- Detecção de OOM por `exit 137` com limite de memória, quando o kernel mata um processo filho.
- Ação desconhecida sugerida pela IA vira `none`: o sistema nunca chuta uma correção.

[Não lançado]: https://github.com/MathZiraA/Hermes-Sentinel-AIOps/commits/main
