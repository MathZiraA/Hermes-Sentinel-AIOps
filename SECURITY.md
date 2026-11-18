# Política de segurança

O Hermes Sentinel lê o estado de clusters Kubernetes e pode, com aprovação humana, alterá-los. Levamos relatos de
segurança a sério.

## Versões suportadas

| Versão | Suporte |
|---|---|
| `1.x` mais recente | ✅ correções de segurança |
| `0.x` | ❌ atualize para a 1.x |

## Como relatar uma vulnerabilidade

**Não abra uma issue pública.** Use o relato privado do GitHub:
[Security → Report a vulnerability](https://github.com/MathZiraA/Hermes-Sentinel-AIOps/security/advisories/new).

Inclua, se puder:

- o componente afetado (backend, servidor MCP, watcher, frontend, scripts);
- passos para reproduzir e o impacto (ex.: alterar o cluster sem aprovação, vazar logs ou tokens);
- a versão ou o commit.

Prazos-alvo: confirmação em até **3 dias úteis**, avaliação inicial em até **7 dias** e correção conforme a gravidade.
Quem relatar de forma responsável recebe crédito no aviso de segurança, se quiser.

## Escopo de maior interesse

- contornar a **aprovação humana** (qualquer caminho que altere o cluster sem o clique do operador);
- um bot usar ferramentas fora do seu papel (contornar `ROLE_TOOLS` ou os tokens por bot);
- **prompt injection** vinda de logs/eventos que leve o agente a agir;
- vazamento de segredos para a IA, para o Hermes Brain ou para logs;
- escrita fora do vault do Hermes Brain (path traversal);
- acesso ao servidor MCP sem token.

## Como o produto se protege hoje

O modelo de ameaças completo está em [docs/security/threat-model.md](docs/security/threat-model.md). Em resumo:

- **Aprovação humana obrigatória** para qualquer mudança no cluster.
- **Menor privilégio por bot**: cada bot tem token próprio e o servidor MCP confere o papel a cada chamada.
- **Logs são dados não confiáveis**: segredos são redigidos e o conteúdo é marcado antes de ir para a IA.
- **Nada exposto à internet**: o MCP escuta só em `127.0.0.1` e o Hermes chega por túnel SSH reverso de saída.
- **Segredos fora do Git**: `.env` ignorado, busca de segredos no CI (gitleaks) e auditoria de dependências (pip-audit).
