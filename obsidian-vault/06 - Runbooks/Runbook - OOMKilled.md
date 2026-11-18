---
tags: [runbook, kubernetes, memoria]
incident_types: [OOMKilled]
severity: alta
---

# Runbook: OOMKilled

## Sintoma
- Pod reinicia com `Last State: Terminated — Reason: OOMKilled` (exit code **137**).
- `kubectl get pods` mostra `RESTARTS` subindo; às vezes vira `CrashLoopBackOff`.

## Diagnóstico
1. `kubectl describe pod <pod> -n <ns>`: confira `Limits.memory` e o `Last State`.
2. `kubectl top pod <pod> -n <ns>`: o consumo encosta no limite?
3. Apps Java: o heap respeita o container? Procure `-XX:MaxRAMPercentage` em `JAVA_TOOL_OPTIONS`.
4. Logs anteriores ao kill: `kubectl logs <pod> -n <ns> --previous --tail=80`.

## Causas comuns
| Causa | Pista |
|---|---|
| Limite de memória baixo demais | Consumo estável perto do limite desde o boot |
| Heap Java maior que o container | `MaxRAMPercentage` ausente ou > 75 |
| Vazamento de memória | Consumo cresce até morrer, sempre no mesmo intervalo |
| Pico de carga | Coincide com HPA escalando / tráfego alto |

## Remediação
- **Imediata (Executor):** `kubectl rollout restart deployment/<deploy> -n <ns>`. Isso só alivia; não resolve um limite mal dimensionado.
- **Correta:** subir `resources.limits.memory` (ex.: 512Mi → 768Mi) e manter `MaxRAMPercentage=60`.
- Se for vazamento, abra issue para o time da aplicação com o heap dump.

## Verificação
- `kubectl get pods -n <ns> -w`: sem novos restarts por 10 min.
- Prova StockFlow: `pedidos` usa `limits.memory: 512Mi` e `MaxRAMPercentage=60`.
