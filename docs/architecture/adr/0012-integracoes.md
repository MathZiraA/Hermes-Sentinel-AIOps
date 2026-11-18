# ADR 0012: Integrações por canais e enriquecimento opcional

- **Status:** aceito
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

Empresas já têm ferramentas: tickets no Jira, alertas no Zabbix, painéis no Grafana, logs no Loki e código no
GitHub ([ADR 0007](0007-produto-self-hosted.md)). O Sentinel precisa conversar com elas sem depender de nenhuma.

## Decisão

- **Saída por canais:** o Jira é um canal registrado em `integrations/notify.py`. Ele cria uma issue por incidente,
  atribui ao plantão com menção, comenta cada etapa e transiciona ao resolver. O escalonamento acontece no Jira.
- **Entrada por webhook:** o Zabbix envia `PROBLEM`/`RESOLVED` para `POST /api/integrations/zabbix`, autenticado por
  token próprio (comparação em tempo constante), com deduplicação por `event_id` e severidade da origem.
- **Enriquecimento:** Loki (logs que sobrevivem ao pod, também como ferramenta MCP), GitHub (commits do deploy
  correlacionado) e Grafana (link com o intervalo do incidente).
- Tudo é **opcional e degradável:** sem configuração, a integração some; com erro, o incidente segue e o erro vai
  para o log.
- Testes usam `httpx.MockTransport`: nenhum teste depende de serviço externo.

## Consequências

- **Positivas:** o Sentinel encaixa no fluxo que o time já usa; alertas de infraestrutura fora do Kubernetes também
  chegam ao Investigator.
- **Negativas:** o Jira é o único canal de aviso, então ninguém é acordado no celular (ver ADR 0007). A menção depende
  de o e-mail do usuário existir no Jira.
