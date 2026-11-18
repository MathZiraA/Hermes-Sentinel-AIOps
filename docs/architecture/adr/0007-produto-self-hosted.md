# ADR 0007: Direção de produto, plataforma AIOps self-hosted

- **Status:** aceito
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

O projeto vai servir de portfólio com qualidade de produto vendável. Foi feita uma entrevista de produto para
definir o escopo antes de investir em persistência, identidade e interface.

## Decisão

| Tema | Decisão |
|---|---|
| Entrega | Self-hosted (a empresa instala no próprio ambiente); vários clusters por instalação, com um agente leve em cada cluster |
| Identidade | Login local + OIDC; papéis Admin, Operador, Visualizador e Auditor; times com escopo por namespace e cluster; 2FA opcional |
| Aprovação | Um operador aprova; quem propôs não aprova a própria proposta; motivo obrigatório ao rejeitar |
| Auditoria | Trilha imutável e exportável |
| Incidentes | SEV1–SEV4 com SLA configurável; ciclo Detectado → Reconhecido → Investigando → Aguardando aprovação → Corrigindo → Monitorando → Resolvido → Post-mortem |
| Operação | Plantão com escalonamento, janelas de manutenção, autorremediação só de baixo risco e configurável, verificação pós-correção |
| Integrações | Jira (ticket por incidente), Zabbix (alertas viram incidentes), Grafana, Loki, GitHub (correlação com deploys) |
| IA | Provedor trocável, Gemini como padrão; orçamento diário com corte; só o Investigator usa IA; avaliação humana de cada RCA |
| Dados | PostgreSQL; memória com busca semântica sincronizada com o Obsidian |
| Interface | Painel profissional como tela principal, escritório isométrico como modo "sala de guerra"; claro/escuro; PT/EN; responsiva |
| Distribuição | Helm chart e Docker Compose; métricas Prometheus e logs estruturados |
| Repositório | Licença MIT; branch + PR para a `main`; Conventional Commits; SemVer; CI obrigatório |

## Consequências

- **Positivas:** escopo claro e ordenado no [ROADMAP](../../../ROADMAP.md).
- **Negativas:** com o Jira como único canal de aviso, o escalonamento de plantão acontece no Jira (reatribuição e
  menção) e não acorda ninguém no celular. Um canal de tempo real pode ser adicionado depois.
