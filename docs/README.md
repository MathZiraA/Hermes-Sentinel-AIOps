# Documentação do Hermes Sentinel

| Para… | Leia |
|---|---|
| Entender o sistema | [Arquitetura](architecture/overview.md) · [Decisões (ADRs)](architecture/adr/) |
| Instalar e configurar | [Instalação](operations/installation.md) · [Configuração](operations/configuration.md) |
| Montar a demonstração com o Hermes | [Ambiente de demonstração](operations/demo-environment.md) |
| Usar no dia a dia | [Manual do usuário](user-guide/README.md) |
| Integrar | [API REST, WebSocket e MCP](api/README.md) · [OpenAPI](api/openapi.json) |
| Avaliar a segurança | [Modelo de ameaças](security/threat-model.md) · [Política de segurança](../SECURITY.md) |
| Contribuir | [CONTRIBUTING](../CONTRIBUTING.md) · [Roadmap](../ROADMAP.md) · [Changelog](../CHANGELOG.md) |

## Decisões de arquitetura

| ADR | Decisão |
|---|---|
| [0001](architecture/adr/0001-registrar-decisoes.md) | Registrar decisões com ADRs |
| [0002](architecture/adr/0002-deteccao-deterministica.md) | Detecção determinística; IA só depois de uma anomalia |
| [0003](architecture/adr/0003-aprovacao-humana.md) | Toda alteração no cluster passa por aprovação humana |
| [0004](architecture/adr/0004-hermes-via-mcp-e-tunel.md) | O Hermes investiga pelo MCP, através de um túnel SSH reverso |
| [0005](architecture/adr/0005-menor-privilegio-por-bot.md) | Um token por bot e permissões por papel |
| [0006](architecture/adr/0006-hermes-brain-obsidian.md) | Memória do time num vault Obsidian |
| [0007](architecture/adr/0007-produto-self-hosted.md) | Direção de produto: plataforma AIOps self-hosted |
| [0008](architecture/adr/0008-persistencia-ciclo-de-vida-auditoria.md) | PostgreSQL, ciclo de vida explícito e auditoria encadeada |
| [0009](architecture/adr/0009-identidade-e-acesso.md) | Identidade: sessões no servidor, RBAC com escopo por time, 2FA e OIDC |
| [0010](architecture/adr/0010-interface-profissional.md) | Interface profissional com painel principal e sala de guerra |
