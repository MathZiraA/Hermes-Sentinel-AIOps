# ADR 0005: Um token por bot e permissões por papel, conferidas no servidor

- **Status:** aceito
- **Data:** 2026-11-17
- **Decisores:** mantenedor

## Contexto

Os cinco agentes aparecem como bots separados no Hermes Desktop. Com um token único, qualquer bot poderia chamar
qualquer ferramenta, e o papel de cada um dependeria só do prompt, que pode ser contornado por prompt injection ou por
uma edição de configuração.

## Decisão

Duas travas independentes:

1. **No Hermes:** cada profile declara `mcp_servers.sentinel.tools.include` com as ferramentas do seu papel; o bot nem
   enxerga as outras.
2. **No Sentinel:** cada bot tem um token próprio (`SENTINEL_MCP_ROLE_TOKENS`). Toda ferramenta chama `_authorize`,
   que compara o token em tempo constante e consulta `ROLE_TOOLS`. Fora do papel, a chamada recebe `ToolError`.

O token principal (`SENTINEL_MCP_TOKEN`) pertence ao Hermes padrão e ao fluxo automático do Sentinel.

## Consequências

- **Positivas:** menor privilégio real; mesmo com o config do bot alterado, o servidor barra.
- **Negativas:** mais tokens para rotacionar (documentado em operação).
