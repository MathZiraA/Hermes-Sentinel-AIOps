# API

O contrato completo está em [`openapi.json`](openapi.json) (gerado por `make openapi`) e, com o backend rodando, em
http://localhost:8000/docs.

Toda rota exige login (cookie `sentinel_session`, HttpOnly), exceto `/api/healthz` e `/api/auth/config`. Cada rota
exige uma permissão do papel (tabela abaixo) e filtra pelo escopo dos times do usuário. Escritas de uma origem fora de
`CORS_ORIGINS` são recusadas.

## Autenticação

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/auth/config` | Público: login habilitado, SSO disponível, instalação sem usuários |
| `POST` | `/api/auth/setup` | Cria o primeiro administrador (só com o banco sem usuários) |
| `POST` | `/api/auth/login` | `{"email", "password", "code"?}`. Com 2FA ativo, sem `code`: 401 `mfa_required`. Bloqueio: 429 |
| `POST` | `/api/auth/logout` | Revoga a sessão |
| `GET` | `/api/auth/me` | Usuário, papel, permissões e escopo |
| `POST` | `/api/auth/password` | `{"current", "new"}`; revoga as outras sessões |
| `POST` | `/api/auth/totp/setup` · `/enable` · `/disable` | Configura o 2FA (segredo + URI `otpauth://` para QR) |
| `GET` | `/api/auth/oidc/login` · `/oidc/callback` | SSO OIDC (Authorization Code + PKCE) |

## Administração (papel Admin)

| Método | Rota | Descrição |
|---|---|---|
| `GET` · `POST` | `/api/admin/users` | Lista e cria usuários (`{"email", "name", "role", "password"?}`) |
| `PATCH` | `/api/admin/users/{id}` | `{"name"?, "role"?, "active"?}`; mudanças de acesso derrubam as sessões |
| `POST` | `/api/admin/users/{id}/password` | Redefine a senha |
| `GET` · `POST` | `/api/admin/teams` | Lista e cria times |
| `PUT` · `DELETE` | `/api/admin/teams/{id}` | `{"members": [e-mails], "scopes": [{"cluster", "namespace"}]}` |

## Permissões por papel

| Permissão | Visualizador | Auditor | Operador | Admin |
|---|:-:|:-:|:-:|:-:|
| ver incidentes, relatórios, clusters, saúde | ✅ | ✅ | ✅ | ✅ |
| reconhecer, aprovar, rejeitar, simular | | | ✅ | ✅ |
| auditoria (ler, verificar, exportar) | | ✅ | | ✅ |
| usuários e times | | | | ✅ |

## REST

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/healthz` | Liveness público (sem detalhes) |
| `GET` | `/api/health` | Kubernetes, gateway do Hermes, Hermes Brain, banco, GitHub, MCP e contadores de IA |
| `GET` | `/api/state` | Último evento de cada agente e aprovações pendentes |
| `GET` | `/api/incidents` | Lista com filtros `status`, `sev`, `cluster`, `q`, `limit`, `offset`; inclui o estado do SLA |
| `GET` | `/api/incidents/{id}` | Detalhe com logs, memória usada e linha do tempo |
| `POST` | `/api/incidents/{id}/acknowledge` | Assumir o incidente (MTTA e SLA de reconhecimento) |
| `POST` | `/api/simulate/incident` | `{"type": "OOMKilled" \| "CrashLoopBackOff" \| "ImagePullBackOff", "useAi": false}` |
| `POST` | `/api/agents/approve/{id}` | Aprova; corpo opcional `{"motivo": "…"}` vira Lição |
| `POST` | `/api/agents/reject/{id}` | Rejeita; `{"motivo": "…"}` é **obrigatório** e vira Lição |
| `POST` | `/api/test-communication` | Supervisor ↔ Monitor com dados reais (0 IA) |
| `GET` | `/api/audit` | Trilha de auditoria (filtro `actor`) |
| `GET` | `/api/audit/verify` | Recalcula a cadeia de hashes e aponta a primeira entrada adulterada |
| `GET` | `/api/audit/export?format=json\|csv` | Exporta a auditoria completa |
| `GET` | `/api/reports/summary?days=30` | MTTA, MTTR, volume por SEV, status, serviço e tipo, e decisões |
| `GET` | `/api/clusters` | Clusters conhecidos e incidentes abertos em cada um |
| `GET` | `/api/clusters/{id}/status` | Nós, workloads, pods saudáveis e estado do Monitor |
| `GET` | `/api/brain/graph` | Notas e wikilinks do Hermes Brain (para o grafo) |
| `GET` | `/api/brain/search?q=` | Busca na memória |
| `GET` | `/api/brain/notes/{nome}` | Conteúdo de uma nota (Markdown) |

### Operação

| Método | Rota | Permissão | Descrição |
|---|---|---|---|
| `GET` | `/api/actions` | leitura | Catálogo de ações, risco e quais podem ser automáticas |
| `GET` · `POST` | `/api/silences` | leitura · Operador/Admin | Janelas de manutenção (`{"namespace", "workload", "type", "startsAt", "endsAt", "reason"}`, curingas `*`) |
| `DELETE` | `/api/silences/{id}` | Operador/Admin | Encerra a janela agora |
| `GET` · `POST` | `/api/policies` | leitura · Admin | Autorremediação (`{"type", "action", "namespace", "workload", "maxPerHour"}`; só ações de baixo risco) |
| `PATCH` · `DELETE` | `/api/policies/{id}` | Admin | Liga/desliga ou apaga a política |
| `GET` · `POST` | `/api/oncall` | leitura · Admin | Turnos de plantão (`{"teamId", "user", "level": 1\|2, "startsAt", "endsAt"}`) |
| `DELETE` | `/api/oncall/{id}` | Admin | Remove um turno |

### Integrações

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/integrations` | Estado de Jira, Zabbix, Grafana, Loki e GitHub |
| `POST` | `/api/integrations/zabbix` | Webhook do Zabbix (`Authorization: Bearer <ZABBIX_WEBHOOK_TOKEN>`); `PROBLEM` abre, `RESOLVED` registra a recuperação |

Cada incidente traz `links` (`grafana`, `logs`, `ticket`, `source`) e, se houver, `ticket` (`{"system", "key", "url"}`).

### Ações de correção

| Ação | Risco | Automática? | Comando |
|---|---|:-:|---|
| `rollout_restart` | baixo | ✅ | `kubectl rollout restart deployment/<w>` |
| `delete_pod` | baixo | ✅ | `kubectl delete pod <pod>` |
| `rerun_job` | baixo | ✅ | novo Job com o mesmo template |
| `scale` | médio | | `kubectl scale … --replicas=1..5` |
| `rollout_undo` | médio | | `kubectl rollout undo deployment/<w>` |
| `set_resources` | médio | | `kubectl set resources … --limits=memory=…,cpu=…` |
| `cordon` | médio | | `kubectl cordon <nó>` |
| `drain` | alto | | `kubectl drain <nó> --ignore-daemonsets` |
| `none` | — | | correção manual |

### Ciclo de vida e severidade

| Status | Significado |
|---|---|
| `detected` | o Monitor abriu o incidente |
| `acknowledged` | uma pessoa assumiu |
| `investigating` | o Investigator está trabalhando |
| `waiting_approval` | correção proposta, esperando decisão humana |
| `remediating` | o Executor está aplicando |
| `monitoring` | aplicado; conferindo se resolveu |
| `resolved` / `postmortem` | resolvido / documentado no Hermes Brain |
| `closed` | correção rejeitada, nada foi alterado |
| `failed` | a correção falhou; precisa de um humano |

SEV1 (fora do ar) a SEV4 (aviso antecipado) vêm do tipo de falha. Os prazos de SLA são configuráveis
([configuração](../operations/configuration.md#banco-de-dados-e-sla)).

## WebSocket `/ws/telemetry`

Mensagens: `snapshot`, `agent`, `health`, `approval_pending`, `approval_resolved`, `pong` (envie `ping` como keepalive).

```json
{
  "type": "agent",
  "timestamp": "2026-11-18T02:52:13.120+00:00",
  "agentId": "executor",
  "agentName": "Executor",
  "role": "Remediação",
  "status": "waiting_approval",
  "targetZone": "WORKSTATION",
  "bubbleMessage": "Correção pronta. Aguardando sua aprovação.",
  "technicalLog": "kubectl rollout restart deployment/pedidos -n stockflow",
  "incidentId": "INC-235215-MIG",
  "kanbanAction": { "op": "move", "cardId": "INC-235215-MIG", "column": "Aguardando aprovação" },
  "approvalRequest": { "incidentId": "INC-235215-MIG", "action": "rollout_restart", "command": "…", "risk": "baixo" }
}
```

## Servidor MCP

Endpoint `http://127.0.0.1:8765/mcp` (Streamable HTTP), com `Authorization: Bearer <token>`.

| Ferramenta | O que faz | monitor / supervisor | investigator | executor | itsm |
|---|---|:-:|:-:|:-:|:-:|
| `cluster_status` | Contexto, versão, nós e pods com problema | ✅ | ✅ | ✅ | ✅ |
| `listar_pods` | Pods com fase, prontidão, reinícios e motivo | ✅ | ✅ | ✅ | ✅ |
| `visao_geral` | Deployments, statefulsets, jobs, PVCs, HPAs e services | ✅ | ✅ | ✅ | ✅ |
| `memoria_buscar` / `memoria_ler` | Busca e leitura no Hermes Brain | ✅ | ✅ | ✅ | ✅ |
| `memoria_registrar` | Nota no diário do próprio bot | ✅ | ✅ | ✅ | ✅ |
| `ler_logs` | Até 80 linhas, redigidas | | ✅ | ✅ | |
| `descrever_pod` | Resumo de `kubectl describe pod` | | ✅ | ✅ | |
| `listar_eventos` | Eventos do namespace (Warning por padrão) | | ✅ | ✅ | ✅ |
| `descrever_recurso` | deployment, statefulset, daemonset, job, cronjob, pvc, service, hpa, configmap (só as chaves) | | ✅ | ✅ | |
| `descrever_no` | Condições, capacidade, taints e uso do nó | | ✅ | ✅ | |
| `uso_recursos` | Uso real vs. limite por container | | ✅ | ✅ | |
| `buscar_logs_loki` | Logs centralizados do workload (se o Loki estiver configurado) | | ✅ | ✅ | |
| `consultar_runbook` | Runbooks oficiais do tipo de falha | | ✅ | ✅ | ✅ |
| `runbook_rascunho` | Rascunho de runbook (exige revisão humana) | | ✅ | ✅ | ✅ |
| `propor_correcao` | Cria um pedido de aprovação; **não executa nada**. Ações: `rollout_restart`, `scale`, `rollout_undo`, `set_resources`, `none` | | | ✅ | |

O token principal (`SENTINEL_MCP_TOKEN`) tem todas as ferramentas.
