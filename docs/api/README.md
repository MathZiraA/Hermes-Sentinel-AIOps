# API

O contrato completo está em [`openapi.json`](openapi.json) (gerado por `make openapi`) e, com o backend rodando, em
http://localhost:8000/docs.

> Em `0.1.x` a API não tem autenticação e escuta só em `127.0.0.1`. Login e papéis chegam na Fase 2.

## REST

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/health` | Kubernetes, gateway do Hermes, Hermes Brain, GitHub, MCP e contadores de IA |
| `GET` | `/api/state` | Último evento de cada agente e aprovações pendentes |
| `GET` | `/api/incidents` | Incidentes da sessão (sem logs) |
| `POST` | `/api/simulate/incident` | `{"type": "OOMKilled" \| "CrashLoopBackOff" \| "ImagePullBackOff", "useAi": false}` |
| `POST` | `/api/agents/approve/{id}` | Aprova; corpo opcional `{"motivo": "…"}` vira Lição |
| `POST` | `/api/agents/reject/{id}` | Rejeita; corpo opcional `{"motivo": "…"}` vira Lição |
| `POST` | `/api/test-communication` | Supervisor ↔ Monitor com dados reais (0 IA) |

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
| `consultar_runbook` | Runbooks oficiais do tipo de falha | | ✅ | ✅ | ✅ |
| `runbook_rascunho` | Rascunho de runbook (exige revisão humana) | | ✅ | ✅ | ✅ |
| `propor_correcao` | Cria um pedido de aprovação; **não executa nada** | | | ✅ | |

O token principal (`SENTINEL_MCP_TOKEN`) tem todas as ferramentas.
