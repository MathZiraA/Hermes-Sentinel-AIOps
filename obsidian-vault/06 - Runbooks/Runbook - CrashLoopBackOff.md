---
tags: [runbook, kubernetes, disponibilidade]
incident_types: [CrashLoopBackOff, ImagePullBackOff]
severity: alta
---

# Runbook: CrashLoopBackOff

## Sintoma
- Pod em `CrashLoopBackOff`: o container inicia, cai, e o kubelet espera cada vez mais (10s → 5min) para tentar de novo.

## Diagnóstico
1. `kubectl logs <pod> -n <ns> --previous --tail=80`: o erro de quem caiu.
2. `kubectl describe pod <pod> -n <ns>`: `Exit Code`, eventos e probes.
3. Exit codes:
   | Código | Significado |
   |---|---|
   | 1 | Erro da aplicação (config, exceção no boot) |
   | 137 | Morto por sinal: OOMKilled ou liveness probe → veja o runbook **OOMKilled** |
   | 143 | SIGTERM (desligamento normal/forçado) |
4. Mudou algo? `kubectl rollout history deployment/<deploy> -n <ns>`.

## Causas comuns (StockFlow)
- **Banco indisponível:** `pedidos`/`pagamentos` sobem antes do `mysql-0` estar pronto → `Communications link failure`.
- **Secret ausente:** `senhas` não aplicado → `CreateContainerConfigError`.
- **Eureka fora:** gateway sem rotas, mas não costuma derrubar o pod.
- **Liveness agressiva:** `initialDelaySeconds` menor que o boot do Spring (~40–60s).

## Remediação
- **Dependência fora:** resolva a dependência (ex.: `mysql-0`), depois `kubectl rollout restart deployment/<deploy> -n <ns>`.
- **Deploy ruim:** `kubectl rollout undo deployment/<deploy> -n <ns>`.
- **Probe agressiva:** aumente `initialDelaySeconds` ou use `startupProbe`.

## Variante: ImagePullBackOff
- `describe` mostra `Failed to pull image`: tag errada, registry privado ou sem internet.
- Corrija a tag/credencial (`imagePullSecrets`) ou faça `rollout undo`.

## Verificação
- `kubectl get pods -n <ns>`: `READY 1/1` e `RESTARTS` estável.
