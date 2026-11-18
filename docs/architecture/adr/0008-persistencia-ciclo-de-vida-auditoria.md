# ADR 0008: Persistência em PostgreSQL, ciclo de vida explícito e auditoria encadeada

- **Status:** aceito
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

Na 0.1.0 os incidentes viviam em memória: reiniciar o backend perdia pedidos de aprovação e histórico. Não havia
severidade, SLA nem registro de quem decidiu o quê, requisitos básicos para uso em empresa ([ADR 0007](0007-produto-self-hosted.md)).

## Decisão

1. **Banco:** SQLAlchemy 2 assíncrono com migrações Alembic. PostgreSQL em produção (`DATABASE_URL`); SQLite como
   padrão na demo e nos testes. O backend aplica as migrações ao subir (`AUTO_MIGRATE=true`).
2. **Modelo:** colunas para filtrar e relatar (status, SEV, datas, workload, cluster) e o documento completo do
   incidente em JSON. O contrato pydantic continua sendo a fonte da verdade, sem mapeamento duplicado.
3. **Ciclo de vida** em `domain/lifecycle.py`, com transições validadas:
   `detected → acknowledged → investigating → waiting_approval → remediating → monitoring → resolved → postmortem`,
   mais `closed` (rejeitado, sem alteração) e `failed` (precisa de um humano). Reabrir é permitido a partir de
   `monitoring`, `resolved`, `closed` e `failed`.
4. **Reconhecer** é independente do status: registra quem assumiu e quando (MTTA e SLA de reconhecimento).
5. **Severidade** SEV1–SEV4 derivada do tipo de falha, com SLA configurável (`SLA_ACK_MINUTES`, `SLA_RESOLVE_MINUTES`).
6. **Auditoria imutável:** cada entrada carrega o SHA-256 da anterior, e triggers no banco recusam `UPDATE` e `DELETE`.
   `GET /api/audit/verify` recalcula a cadeia; `GET /api/audit/export` exporta em JSON ou CSV.
7. **Retomada:** na subida, incidentes abertos voltam para a memória. Pedidos de aprovação continuam valendo,
   investigações interrompidas recomeçam, e correções interrompidas viram `failed` para um humano conferir.
8. **Separação de deveres:** quem propôs a correção não pode aprová-la nem rejeitá-la.

## Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| Tabelas normalizadas para RCA, aprovação e sinais | Consultas SQL ricas | Mapeamento duplicado do contrato; migrações frequentes |
| Só SQLite | Zero dependências | Não é o que empresas operam; concorrência limitada |
| Log de auditoria só em arquivo | Simples | Fácil de adulterar sem deixar rastro |

## Consequências

- **Positivas:** nada se perde ao reiniciar; base para login, relatórios e integrações; auditoria verificável.
- **Negativas:** o escritor da auditoria é único por processo (lock em memória). Rodar várias réplicas do backend
  exigirá um lock no banco (`pg_advisory_xact_lock`), previsto para a Fase 7.
