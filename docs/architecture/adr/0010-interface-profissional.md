# ADR 0010: Interface profissional com painel principal e sala de guerra

- **Status:** aceito
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

A interface era uma única tela: o escritório isométrico. Ótima para demonstrar, mas sem lugar para triagem, histórico,
relatórios, auditoria e administração, nem para uso no celular ([ADR 0007](0007-produto-self-hosted.md)).

## Decisão

- **Painel como tela principal**, com navegação lateral por seção (Operação, Governança, Administração) que mostra só
  o que o papel do usuário permite. O escritório virou a **Sala de guerra**, uma das telas.
- **Telas:** Visão geral, Incidentes (filtros na URL, tabela no desktop e cartões no celular), detalhe do incidente
  (decisão com o comando exato e motivo, causa raiz, evidências, linha do tempo, logs, memória usada), Clusters,
  Hermes Brain (busca, grafo e leitor de notas), Relatórios, Auditoria, Usuários, Times e Minha conta (senha e 2FA).
- **Dados:** React Query com atualização periódica, e cada evento do WebSocket invalida as consultas na hora.
- **Tema** escuro por padrão (centro de operações) e claro opcional, aplicado antes da primeira pintura.
  **Idioma** PT/EN num dicionário tipado: o TypeScript recusa uma chave que falte em inglês.
- **Marca:** escudo com linha de pulso (vigiar + saúde do sistema), azul primário da paleta existente e escala de
  severidade fixa (SEV1 vermelho, SEV2 laranja, SEV3 amarelo, SEV4 azul) nos dois temas.
- **Sem dependências novas:** o grafo do Hermes Brain é uma simulação de forças em canvas e as notas usam um
  renderizador de Markdown próprio que gera só elementos React (sem HTML cru, sem XSS).

## Consequências

- **Positivas:** fluxo completo de operação no navegador e no celular; a demonstração visual continua disponível.
- **Negativas:** o renderizador de Markdown cobre o subconjunto que o Hermes Brain usa (títulos, listas, citações,
  tabelas, código, negrito e wikilinks), não o CommonMark inteiro.
