# ADR 0004: O Hermes investiga pelo MCP, através de um túnel SSH reverso

- **Status:** aceito (ambiente de demonstração; o modo produto terá um agente por cluster, Fase 7)
- **Data:** 2026-11-17
- **Decisores:** mantenedor

## Contexto

O agente de IA (Hermes) roda 24/7 num VPS compartilhado com outra aplicação em produção (FlowGest), que não pode ser
afetada. O cluster Kubernetes roda no notebook, atrás de NAT. Abrir portas no roteador exporia o cluster à internet.

## Decisão

- O notebook abre um **túnel SSH reverso de saída** (`ssh -R`) para o VPS, mantido por um serviço systemd do usuário.
- A ponta do túnel no VPS escuta apenas no IP da bridge Docker do Hermes; o UFW libera só o IP do container.
- O usuário SSH do túnel não tem shell, e a chave só pode abrir aquela porta (`permitlisten`, `restrict`).
- No notebook, o **servidor MCP do Sentinel** escuta só em `127.0.0.1` e exige `Authorization: Bearer`.
- O Hermes recebe só um **ponteiro** para o incidente e decide o que ler pelas ferramentas MCP, sem receber logs no
  prompt.

## Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| Rodar o cluster no VPS | Sem túnel | Consumiria a memória do FlowGest |
| Abrir porta no roteador | Simples | Cluster exposto à internet |
| VPN (WireGuard/Tailscale) | Robusto | Mais uma peça para operar; acesso mais amplo que o necessário |

## Consequências

- **Positivas:** nada exposto à internet; o FlowGest não é tocado; o Hermes vê só o que as ferramentas permitem.
- **Negativas:** notebook desligado significa Hermes sem cluster (ele avisa); a demonstração depende do túnel.
