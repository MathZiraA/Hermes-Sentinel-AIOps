# ADR 0001: Registrar decisões de arquitetura com ADRs

- **Status:** aceito
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

O projeto saiu de uma demonstração e virou produto. Decisões importantes (onde a IA roda, como o cluster é acessado,
o que exige aprovação) estavam só no histórico de conversas e no código. Quem chega ao repositório não tem como
entender por que as coisas são como são.

## Decisão

Registrar cada decisão relevante de arquitetura, segurança ou contrato público como um ADR curto em
`docs/architecture/adr/`, numerado e imutável. Uma decisão que muda gera um ADR novo, que substitui o anterior; o
antigo nunca é apagado.

## Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| Só comentários no código | Perto do código | Não explica decisões que cruzam componentes |
| Wiki do GitHub | Fácil de editar | Fora do versionamento e da revisão de PR |

## Consequências

- **Positivas:** histórico de decisões revisado junto com o código; onboarding mais rápido.
- **Negativas:** um pouco de escrita a mais por PR relevante.
