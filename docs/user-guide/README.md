# Manual do usuário

Para quem opera o Hermes Sentinel no dia a dia. Versão `0.1.x`.

## Entrar

- **Primeira vez:** a tela de login oferece criar o administrador da instalação.
- **Login:** e-mail e senha, ou **Entrar com SSO** se a empresa configurou um provedor.
- **2FA:** recomendado para quem aprova correções. Ative em **Minha conta** com qualquer aplicativo autenticador
  (Google Authenticator, Authy, 1Password…).

| Papel | Pode |
|---|---|
| Visualizador | acompanhar incidentes, relatórios e a saúde do cluster |
| Operador | também reconhecer, aprovar, rejeitar e simular |
| Auditor | acompanhar e consultar/exportar a auditoria |
| Admin | tudo, inclusive usuários e times |

Cada time enxerga e opera só os clusters e namespaces do seu escopo.

## As telas

| Tela | Para quê |
|---|---|
| **Visão geral** | Incidentes abertos, aprovações pendentes, MTTA/MTTR e saúde do cluster num relance |
| **Incidentes** | Lista com filtros (abertos, aguardando aprovação, encerrados, severidade, busca). Os filtros ficam na URL, dá para compartilhar o link |
| **Detalhe do incidente** | Decisão (comando exato + motivo), causa raiz, evidências, linha do tempo, logs, eventos e a memória que o Investigator usou |
| **Clusters** | Nós, workloads, pods saudáveis e o estado das integrações (Kubernetes, Hermes, MCP, banco, Hermes Brain, GitHub) |
| **Sala de guerra** | O escritório isométrico com os cinco agentes trabalhando ao vivo |
| **Hermes Brain** | Busca na memória, grafo interativo e leitor de notas com os `[[links]]` clicáveis |
| **Relatórios** | Volume por severidade, serviços e tipos de falha mais frequentes, MTTA/MTTR e decisões humanas (7, 30 ou 90 dias) |
| **Auditoria** | Trilha imutável, verificação de integridade e exportação CSV/JSON (Auditor e Admin) |
| **Usuários / Times** | Contas, papéis, desativação e o escopo de cada time (Admin) |
| **Minha conta** | Trocar a senha e ligar o 2FA |

No topo: conexão ao vivo, aviso de aprovações pendentes, idioma (PT/EN) e tema claro/escuro. No celular, o menu abre
pelo botão ☰ e as tabelas viram cartões.

## O time

| Agente | Zona | Papel |
|---|---|---|
| Monitor | Agent Factory | Detecta o problema (sem IA) |
| Supervisor | Central Hub | Coordena e explica em linguagem simples |
| Investigator | Whiteboard | Encontra a causa raiz com o Hermes e a memória do time |
| Executor | Workstation | Prepara a correção e espera a sua aprovação |
| ITSM | Vault / Kanban | Registra o incidente no Hermes Brain e fecha o ciclo |

## Responder a um incidente

1. O incidente aparece na **Visão geral** e o topo avisa quando há aprovação pendente.
2. Abra o incidente e clique em **Assumir**: isso registra quem está cuidando (conta para o SLA).
3. Acompanhe a linha do tempo enquanto o Investigator trabalha (ou assista na **Sala de guerra**).
4. Em **Decisão humana necessária**, leia a causa, as evidências e o **comando exato**.
5. Escreva o **motivo** (obrigatório para rejeitar) e clique em **Aprovar e aplicar** ou **Rejeitar**.

O motivo vira uma Lição que o time lê antes de investigar o próximo caso parecido. Quem propôs uma correção não pode
decidir sobre ela.

## Ações de correção

| Ação | Comando | Quando faz sentido |
|---|---|---|
| `rollout_restart` | `kubectl rollout restart deployment/…` | Falha passageira, dependência já recuperada |
| `scale` | `kubectl scale deployment/… --replicas=N` (1 a 5) | Falta de capacidade |
| `delete_pod` | `kubectl delete pod …` | Um pod travado; o controller recria |
| `none` | nenhuma | Reiniciar não resolve (config, imagem, volume, limite baixo): correção manual |

## Treinar o time pelo Hermes Brain

Abra o vault no Obsidian ([instalação](../operations/installation.md#abrir-o-hermes-brain-no-obsidian)).

- **Lições** (`05 - Lições`): escreva regras suas, por exemplo "nunca reiniciar o mysql em horário comercial".
  Mencione o serviço ou o padrão com `[[nome]]` para a lição chegar aos casos certos.
- **Runbooks** (`06 - Runbooks`): revise os rascunhos dos bots em `Rascunhos/`. Para oficializar, mova o arquivo para
  `06 - Runbooks` e renomeie para `Runbook - <Tipo>.md`.
- **Serviços** (`02 - Serviços`): use a seção "Notas" para dar contexto ("este serviço depende do mysql").

## Conversar com os bots

No Hermes Desktop, escolha o bot (monitor, supervisor, investigator, executor ou itsm) e converse. Pergunte, por
exemplo, "como está o cluster?" ao Monitor ou "por que o estoque-sync caiu?" ao Investigator. Se o Executor propuser
uma correção, ela aparece na tela do Sentinel para aprovação.

## Simulação

Na **Sala de guerra**, o botão **Simular Incidente** cria um incidente fictício (OOMKilled, CrashLoop ou ImagePull) sem tocar no cluster. Com
**Usar IA** desligado, não gasta cota.
