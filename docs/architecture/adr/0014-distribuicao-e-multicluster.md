# ADR 0014: Distribuição em contêineres e multicluster por agente de saída

- **Status:** aceito; substitui o túnel do [ADR 0004](0004-hermes-via-mcp-e-tunel.md) como modo de produção (o túnel
  continua na demonstração)
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

Uma empresa instala o produto no próprio ambiente e opera vários clusters ([ADR 0007](0007-produto-self-hosted.md)).
Ela precisa de imagens, de uma forma padrão de instalar e de observar o próprio Sentinel. Também não pode expor a API
dos clusters remotos nem entregar os kubeconfigs deles a um sistema central.

## Decisão

1. **Imagens:** backend (Python 3.13 slim, UID 10001, logs JSON, healthcheck; a mesma imagem roda o agente) e
   interface (TanStack Start como servidor Node, UID 1000). O build da interface troca o preset do Nitro para
   `node-server` por variável, sem mexer na configuração do Lovable.
2. **Docker Compose** com PostgreSQL, backend, interface e Caddy (uma origem só, cabeçalhos de segurança, `/metrics`
   fechado). **Helm chart** com RBAC de menor privilégio, pods sem root, PostgreSQL embutido opcional, Ingress e
   ServiceMonitor.
3. **Multicluster por agente:** cada cluster remoto roda `python -m agent`, que só faz conexões de saída para a
   central, autenticado por um token próprio (só o hash fica no banco). O agente envia sinais já enriquecidos e
   executa apenas comandos de correção aprovados na central, entregues uma única vez, verificando o resultado.
4. **Observabilidade:** métricas Prometheus (`/metrics`, só na rede interna), logs JSON e probes de liveness e
   readiness.
5. **Release:** uma tag `vX.Y.Z` publica as imagens no GHCR e cria a release com o chart empacotado e as notas do
   CHANGELOG.

## Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| Central com kubeconfig de todos os clusters | Simples | Credenciais concentradas; exige expor a API de cada cluster |
| Service mesh / VPN entre clusters | Transparente | Peça pesada para operar; acesso mais amplo que o necessário |
| Agente com escuta (pull pela central) | Latência menor | Porta aberta em cada cluster remoto |

## Consequências

- **Positivas:** instalação padrão de mercado; clusters remotos sem portas abertas; o Sentinel é observável como
  qualquer serviço.
- **Negativas:** a investigação agêntica pelo MCP vale só para o cluster da central; nos remotos, o Investigator
  usa os logs e o describe que o agente envia. O backend continua com uma réplica (escritor único).
