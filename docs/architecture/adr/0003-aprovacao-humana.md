# ADR 0003: Toda alteração no cluster passa por aprovação humana

- **Status:** aceito (a Fase 4 vai permitir exceções de baixo risco configuradas por um Admin)
- **Data:** 2026-11-17
- **Decisores:** mantenedor

## Contexto

Diagnósticos de IA erram. Um `rollout restart` no serviço errado, ou repetido em loop, pode transformar um incidente
pequeno num grande. Times de operação só confiam em automação que eles controlam.

## Decisão

- Os agentes **propõem**; só o **Executor** aplica, e só depois do clique de um operador.
- As ações possíveis são uma lista fechada (`rollout_restart`, `scale` de 1 a 5 réplicas, `delete_pod`, `none`).
  Uma ação desconhecida vinda da IA vira `none`.
- A ferramenta MCP `propor_correcao` nunca executa nada: cria um pedido de aprovação na tela do Sentinel.
- O motivo da decisão humana é gravado como Lição no Hermes Brain e entra no contexto das próximas investigações.

## Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| Autorremediação total | MTTR mínimo | Risco alto; sem confiança do time |
| Só recomendação, sem botão | Seguro | Operador precisa digitar comandos; perde rastreabilidade |

## Consequências

- **Positivas:** segurança e rastreabilidade; o time aprende com as decisões humanas.
- **Negativas:** o tempo de correção depende de um humano disponível (por isso plantão e escalonamento na Fase 4).
