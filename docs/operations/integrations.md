# Integrações

Todas são opcionais e ligadas por variáveis de ambiente ([configuração](configuration.md#integrações)). O estado de
cada uma aparece em **Clusters → Integrações** e em `GET /api/integrations`.

## Jira (ticket por incidente)

O plano gratuito do Jira Cloud atende até 10 usuários e tem a API necessária.

1. Crie um token de API em https://id.atlassian.com/manage-profile/security/api-tokens (com uma conta de serviço,
   de preferência).
2. Defina `JIRA_URL` (ex.: `https://empresa.atlassian.net`), `JIRA_EMAIL`, `JIRA_API_TOKEN` e `JIRA_PROJECT_KEY`.
   Opcional: `JIRA_ISSUE_TYPE` (padrão `Task`) e `JIRA_DONE_TRANSITION` (nome da transição de fechamento, padrão
   `Done`; em projetos em português costuma ser `Concluído`).

O que acontece:

| Momento | No Jira |
|---|---|
| Incidente aberto | Issue criada (prioridade pela severidade: SEV1 → Highest … SEV4 → Low), atribuída ao plantão primário com menção |
| Escalonamento | Reatribuída ao próximo nível, com comentário e menção |
| Aguardando aprovação, autorremediação, reabertura | Comentário com o comando e o contexto |
| Resolvido ou rejeitado | Comentário e transição para o status de conclusão |
| Falhou | Comentário; a issue fica aberta para um humano |

Incidentes simulados não abrem ticket (a menos que `JIRA_INCLUDE_SIMULATED=true`). Uma falha do Jira nunca para o fluxo
do incidente.

## Zabbix (alertas viram incidentes)

1. Gere um token: `openssl rand -hex 32` e defina `ZABBIX_WEBHOOK_TOKEN` no Sentinel.
2. No Zabbix, crie um **media type** do tipo *Webhook* com os parâmetros `URL` (ex.: `https://sentinel.empresa/api/integrations/zabbix`),
   `Token`, `event_id={EVENT.ID}`, `status={EVENT.STATUS}`, `host={HOST.NAME}`, `trigger={EVENT.NAME}`,
   `severity={EVENT.SEVERITY}`, `message={ALERT.MESSAGE}`, `namespace={EVENT.TAGS.namespace}`,
   `workload={EVENT.TAGS.workload}` e `event_url={$ZABBIX.URL}/tr_events.php?triggerid={TRIGGER.ID}&eventid={EVENT.ID}`,
   e este script:

```javascript
var p = JSON.parse(value);
var req = new HttpRequest();
req.addHeader('Content-Type: application/json');
req.addHeader('Authorization: Bearer ' + p.Token);
var body = {};
['event_id','status','host','trigger','severity','message','namespace','workload','event_url'].forEach(function (k) {
  if (p[k] && p[k].indexOf('{') !== 0) body[k] = p[k];
});
var resp = req.post(p.URL, JSON.stringify(body));
if (req.getStatus() !== 202) throw 'Sentinel respondeu ' + req.getStatus() + ': ' + resp;
return 'OK';
```

3. Crie uma ação de trigger que envie para esse media type (problema **e** recuperação).

Severidade: Disaster → SEV1, High → SEV2, Average → SEV3, Warning/Information → SEV4. O mesmo `event_id` nunca abre
dois incidentes, e a recuperação (`RESOLVED`) entra na linha do tempo do incidente aberto. Janelas de manutenção
valem também para alertas do Zabbix (tipo `ZabbixAlert`).

## Grafana

`GRAFANA_URL` liga o link **Painel no Grafana** em cada incidente, cobrindo de 30 minutos antes da detecção até a
resolução. Com `GRAFANA_DASHBOARD_UID`, o link abre esse painel com as variáveis `namespace` e `workload`; sem ele,
abre o Explore.

## Loki (logs centralizados)

`LOKI_URL` (e `LOKI_TOKEN`, se o Loki exigir) faz o Monitor anexar ao incidente os últimos 30 minutos de logs do
workload, que sobrevivem a pods recriados, e libera a ferramenta MCP `buscar_logs_loki` para o Investigator.
`LOKI_SELECTOR` ajusta os rótulos (padrão `{namespace="{namespace}", app="{workload}"}`).

## GitHub (commits do deploy)

Com `GITHUB_TOKEN` e `GITHUB_DEPLOY_REPOS` (ex.: `pedidos=empresa/pedidos,pagamentos=empresa/pagamentos`), um incidente
que começou logo depois de um rollout mostra os commits recentes do repositório daquele workload.
