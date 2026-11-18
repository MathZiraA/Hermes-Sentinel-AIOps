# Roadmap

O objetivo é levar o Hermes Sentinel de demonstração a **produto self-hosted** que uma empresa possa instalar e operar.
Cada fase é entregue numa branch com PR e termina com a `main` funcionando. As decisões de produto que guiam este plano
estão em [ADR 0007](docs/architecture/adr/0007-produto-self-hosted.md).

| Fase | Tema | Entregas principais | Status |
|---|---|---|---|
| 0 | Fundação do repositório | Estrutura, licença MIT, documentação, CI (lint, tipos, testes, auditoria, segredos), templates, Conventional Commits | 🚧 em andamento |
| 1 | Persistência e domínio | PostgreSQL + migrações, ciclo de vida completo do incidente, SEV1–SEV4 com SLA, auditoria imutável, modelo multicluster | ⏳ |
| 2 | Identidade e acesso | Login local + OIDC, papéis Admin/Operador/Visualizador/Auditor, times com escopo por namespace e cluster, 2FA opcional, separação de deveres | ⏳ |
| 3 | Interface profissional | Painel com incidentes, saúde dos clusters, Hermes Brain com grafo, relatórios; temas claro/escuro; PT/EN; celular; escritório como "sala de guerra" | ⏳ |
| 4 | Operação | Plantão e escalonamento, janelas de manutenção, novas ações (rollout undo, limites, cordon/drain, rerun de job), autorremediação de baixo risco configurável, verificação pós-correção, correlação com deploys | ⏳ |
| 5 | Integrações | Jira (ticket por incidente), Zabbix (alertas viram incidentes), Grafana, Loki, GitHub | ⏳ |
| 6 | IA | Provedor de IA trocável (Gemini padrão), orçamento diário com corte, avaliação humana do diagnóstico, memória em Postgres com busca semântica sincronizada com o Obsidian | ⏳ |
| 7 | Distribuição | Agente por cluster, Helm chart, Docker Compose, métricas Prometheus, documentação completa e release `v1.0.0` | ⏳ |

Sugestões entram como issue do tipo *feature request*.
