# ADR 0006: Memória do time num vault Obsidian (Hermes Brain)

- **Status:** aceito; será complementado por Postgres com busca semântica na Fase 6 (o Obsidian continua como visualização)
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

Não é possível retreinar o modelo de IA, mas o time precisa aprender: lembrar casos parecidos, respeitar decisões
humanas e acumular runbooks. A memória precisa ser legível e editável por pessoas, e visual para demonstração.

## Decisão

- A memória de longo prazo é um vault Obsidian próprio (separado de qualquer vault pessoal), com pastas para Equipe,
  Serviços, Padrões, Incidentes, Lições, Runbooks, Diário dos bots e Cluster, ligadas por `[[wikilinks]]`.
- O Sentinel escreve a nota de cada incidente e atualiza Serviço e Padrão; decisões humanas com motivo viram Lições.
- Antes de investigar, o Investigator recebe os casos e as Lições do mesmo padrão e serviço.
- Os bots leem e escrevem pelas ferramentas MCP, presos ao vault: nomes saneados, caminhos verificados, limite de
  tamanho e de notas por hora. Rascunhos de runbook só viram oficiais com revisão humana.

## Consequências

- **Positivas:** aprendizado visível e auditável; a pessoa ensina o time editando Markdown.
- **Negativas:** busca por palavras (não semântica) e arquivos locais; resolvidos na Fase 6.
