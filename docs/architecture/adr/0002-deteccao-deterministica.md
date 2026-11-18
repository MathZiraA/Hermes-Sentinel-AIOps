# ADR 0002: Detecção determinística; IA só depois de uma anomalia

- **Status:** aceito
- **Data:** 2026-11-17
- **Decisores:** mantenedor

## Contexto

O modelo usado (Gemini no plano gratuito) tem cota pequena e responde 429/503 sob demanda alta. Vigiar o cluster com IA
gastaria a cota com o cluster saudável e tornaria a detecção lenta e imprevisível. Também precisamos que a detecção
seja auditável: "por que isso virou incidente?".

## Decisão

O **Monitor** é código determinístico, sem IA:

- um *watch* de Pods reage em segundos a falhas de container;
- uma varredura a cada 30 s cobre nós, deployments, statefulsets, jobs, PVCs, HPAs, eventos Warning e memória perto do
  limite, além das regras que dependem de tempo (Pending há mais de 2 min, não pronto há mais de 3 min);
- a regra é "qualquer coisa fora do normal": um motivo de espera desconhecido vira incidente com o próprio nome;
- sinais do mesmo workload se juntam num único incidente, e o mesmo sinal tem 10 min de dedupe.

A IA só entra **depois** que o Monitor abre um incidente, e só no Investigator.

## Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| IA lendo métricas continuamente | Pega padrões sutis | Cota, custo, latência, falsos positivos difíceis de explicar |
| Lista fechada de falhas conhecidas | Simples | Deixa passar tudo que não está na lista |

## Consequências

- **Positivas:** custo zero de IA com o cluster saudável; detecção rápida, testável e explicável.
- **Negativas:** anomalias que só aparecem em métricas de aplicação (latência, 5xx) dependem de integrar o
  Prometheus/Zabbix (Fase 5).
