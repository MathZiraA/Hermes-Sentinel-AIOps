# ADR 0013: Provedor de IA trocável, orçamento diário, avaliação humana e memória indexada

- **Status:** aceito; complementa o [ADR 0006](0006-hermes-brain-obsidian.md)
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

Empresas usam provedores diferentes (ou precisam de um modelo local por exigência de dados), querem controlar o gasto
e precisam saber se a IA acerta. A busca da memória por palavras não escala e não entende acento nem sinônimo.

## Decisão

1. **Provedor por configuração** (`AI_PROVIDER`): `hermes` (padrão; investigação agêntica pelo MCP),
   `openai` (qualquer API compatível: OpenAI, Claude pelo endpoint compatível, Ollama, vLLM, LM Studio) e `gemini`
   (direto). Fora do Hermes, a investigação usa o diagnóstico com logs no prompt (sem agente).
2. **Só o Investigator usa IA**; Monitor, Executor e ITSM são determinísticos ([ADR 0002](0002-deteccao-deterministica.md)).
3. **Orçamento diário** (`AI_DAILY_CALL_LIMIT`, `AI_DAILY_TOKEN_LIMIT`) contado no banco por dia e provedor. Ao
   estourar, a chamada nem sai: o diagnóstico cai para os runbooks e o bloqueio é contado. Custo estimado por
   `AI_COST_INPUT_PER_1K`/`AI_COST_OUTPUT_PER_1K`.
4. **Avaliação humana do diagnóstico:** Operadores marcam a causa raiz como certa ou errada. Um "errado" exige
   explicação, que vira Lição no Hermes Brain. Os relatórios mostram a taxa de acerto por fonte.
5. **Memória indexada no banco:** o vault é sincronizado a cada minuto (por data de modificação) para `brain_notes`.
   A busca usa BM25 sem acento (título com peso dobrado) e, com `AI_EMBEDDINGS=true`, uma pontuação híbrida com
   similaridade de embeddings.

## Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| Banco como única fonte da memória | Uma fonte só | Perde a edição humana no Obsidian, que é como o time ensina os bots |
| pgvector | Busca vetorial no banco | Exige extensão no PostgreSQL; o vault cabe em memória com folga hoje |
| Sincronia nos dois sentidos | Editar em qualquer lugar | Conflitos de edição; complexidade sem ganho real |

## Consequências

- **Positivas:** a empresa escolhe o modelo, inclusive local; o custo tem teto; o acerto é medido; a busca melhora.
- **Negativas:** com o vault muito grande (dezenas de milhares de notas), a busca em memória deve migrar para
  pgvector ou PostgreSQL FTS.
