# ADR 0011: Operação: catálogo de ações, verificação, silêncios, autorremediação e plantão

- **Status:** aceito
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

Com só três ações (reiniciar, escalar, apagar pod), o produto propunha reiniciar até quando reiniciar não resolve.
Não havia como confirmar que uma correção funcionou, como silenciar um deploy planejado nem quem avisar quando ninguém
reage. Essas são as rotinas de qualquer time de operação ([ADR 0007](0007-produto-self-hosted.md)).

## Decisão

1. **Catálogo de ações** em `domain/actions.py`: `rollout_restart`, `delete_pod`, `rerun_job` (risco baixo);
   `scale`, `rollout_undo`, `set_resources`, `cordon` (médio); `drain` (alto); `none`. Cada ação valida os seus
   parâmetros (réplicas de 1 a 5; memória até 16Gi; CPU até 8 núcleos) e gera o comando `kubectl` equivalente. É a mesma
   fonte para o orquestrador, o MCP e os prompts. Uma ação inválida vira correção manual, nunca um chute.
2. **Verificação pós-correção:** depois de aplicar, o incidente fica em `monitoring` e o Sentinel confere a saúde do
   alvo (réplicas prontas, Job reexecutado concluído, nó Ready). Saudável: `resolved`. Não saudável: reabre uma vez para
   nova investigação, com o fato no contexto; na segunda vez, `failed` para um humano.
3. **Silêncios (janelas de manutenção):** filtro por cluster, namespace, workload e tipo, com curingas, duração
   máxima de 30 dias e motivo obrigatório. Sinais silenciados não viram incidente.
4. **Autorremediação** só para ações de baixo risco, só onde um Admin criou uma política (tipo de falha + escopo),
   com limite por hora. Ao estourar o limite, volta a pedir aprovação humana. Cada execução é auditada como
   `politica:<id>` e não vira Lição.
5. **Plantão e escalonamento:** turnos por time (primário e secundário). Ao abrir: avisa o primário (ou, sem turno, o
   time do escopo). Sem reconhecimento no prazo de SLA: secundário. No dobro do prazo: administradores. Sem
   responsável nenhum, vai direto aos administradores.
6. **Correlação com deploys:** se o workload teve um rollout nos últimos `DEPLOY_CORRELATION_MINUTES`, a revisão e a
   troca de imagem entram na linha do tempo e no contexto do Investigator, que passa a considerar `rollout_undo`.
7. **Notificações** passam por `integrations/notify.py`, um registro de canais. Um canal com erro nunca para o fluxo.
   O Jira entra na Fase 5.

## Consequências

- **Positivas:** correções certas para cada caso (limite, rollback, nó, job), confirmação de que resolveu, menos
  ruído em manutenção e ninguém sem resposta.
- **Negativas:** `drain` respeita PodDisruptionBudgets e pode falhar parcialmente (o resultado mostra quantos pods
  saíram). A janela de verificação atrasa o fechamento em cerca de `VERIFY_DELAY_SECONDS`.
