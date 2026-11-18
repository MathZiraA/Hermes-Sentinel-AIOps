# Instalação com Helm (Kubernetes)

O chart em [`deploy/helm/hermes-sentinel`](../../deploy/helm/hermes-sentinel) instala a **central** (API, Monitor,
interface) no cluster principal e, nos outros clusters, só o **agente**.

## Central

```bash
helm install sentinel deploy/helm/hermes-sentinel -n sentinel --create-namespace \
  --set central.publicUrl=https://sentinel.empresa.com \
  --set central.namespaces='{loja,pagamentos}' \
  --set ingress.enabled=true --set ingress.host=sentinel.empresa.com \
  --set ingress.className=nginx
```

| Valor | Para quê |
|---|---|
| `central.namespaces` | Namespaces vigiados |
| `central.existingSecret` | Secret com `DATABASE_URL`, `SENTINEL_SECRET_KEY` e chaves de IA/integrações (produção). Vazio: o chart gera um Secret e usa o PostgreSQL embutido |
| `central.env` | Variáveis não secretas (`AI_PROVIDER`, `SLA_*`, `GRAFANA_URL`, …) |
| `postgresql.enabled` | PostgreSQL embutido (avaliação). Em produção, `false` + banco gerenciado |
| `rbac.remediation` | `false` instala em modo só-leitura: o Sentinel recomenda, mas não aplica |
| `metrics.serviceMonitor.enabled` | ServiceMonitor para o Prometheus Operator |

**Permissões (RBAC):** leitura de pods, logs, eventos, workloads, jobs, PVCs, HPAs, nós e métricas. Escrita, só com
`rbac.remediation=true`, limitada às ações do catálogo: `patch` em deployments e `deployments/scale`, `delete` em
pods, `create` em `pods/eviction` e jobs, e `patch` em nós. **Secrets nunca são lidos.**

**Segurança dos pods:** sem root, `allowPrivilegeEscalation: false`, todas as capabilities removidas e seccomp
`RuntimeDefault`. O backend roda com uma réplica e estratégia `Recreate` (escritor único da auditoria, [ADR 0008](../architecture/adr/0008-persistencia-ciclo-de-vida-auditoria.md)).

## Clusters remotos (agente)

1. Na central (Admin): `POST /api/admin/clusters` com `{"id": "loja-prod", "name": "Loja (produção)"}`. A resposta
   traz o token do agente **uma única vez**.
2. No cluster remoto:

```bash
kubectl create namespace sentinel
kubectl -n sentinel create secret generic agent-token --from-literal=SENTINEL_AGENT_TOKEN=sca_…
helm install sentinel-agent deploy/helm/hermes-sentinel -n sentinel \
  --set central.enabled=false --set postgresql.enabled=false \
  --set agent.enabled=true --set agent.centralUrl=https://sentinel.empresa.com \
  --set agent.existingSecret=agent-token --set agent.namespaces='{loja}'
```

O agente roda o mesmo Monitor, envia os sinais com logs, describe e deploy recente, e busca a cada 10 s as correções
**aprovadas na central**. Depois de aplicar, ele verifica a saúde do alvo e responde. Toda conexão é de saída: nada
fica exposto no cluster remoto, e a central nunca recebe o kubeconfig dele. Detalhes no
[ADR 0014](../architecture/adr/0014-distribuicao-e-multicluster.md).

## Observabilidade do Sentinel

| Métrica | Tipo | Rótulos |
|---|---|---|
| `sentinel_incidents_total` | counter | `type`, `sev`, `source` |
| `sentinel_incident_transitions_total` | counter | `to` |
| `sentinel_decisions_total` | counter | `decision`, `auto` |
| `sentinel_remediations_total` | counter | `action`, `result` |
| `sentinel_detections_total` | counter | `type`, `outcome` |
| `sentinel_ai_calls_total` / `sentinel_ai_latency_seconds` | counter / histogram | `provider`, `outcome` |
| `sentinel_open_incidents` | gauge | `sev` |
| `sentinel_websocket_clients` | gauge | — |

Logs em JSON (`LOG_FORMAT=json`, padrão nas imagens), prontos para Loki ou Elasticsearch. Probes: `/api/healthz`
(liveness) e `/api/readyz` (readiness: banco acessível).
