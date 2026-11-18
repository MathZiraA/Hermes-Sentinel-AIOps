# Manual do usuário

Para quem opera o Hermes Sentinel no dia a dia. Versão `0.1.x`.

## Entrar

- **Primeira vez:** a tela de login oferece criar o administrador da instalação.
- **Login:** e-mail e senha, ou **Entrar com SSO** se a empresa configurou um provedor.
- **2FA:** recomendado para quem aprova correções. Ative em **Minha conta** (Fase 3) ou pela API
  `/api/auth/totp/setup`, com qualquer aplicativo autenticador (Google Authenticator, Authy, 1Password…).

| Papel | Pode |
|---|---|
| Visualizador | acompanhar incidentes, relatórios e a saúde do cluster |
| Operador | também reconhecer, aprovar, rejeitar e simular |
| Auditor | acompanhar e consultar/exportar a auditoria |
| Admin | tudo, inclusive usuários e times |

Cada time enxerga e opera só os clusters e namespaces do seu escopo.

## A tela principal

| Área | O que mostra |
|---|---|
| **Escritório** (centro) | Os cinco agentes trabalhando. Cada um anda até a sua zona e fala em balões de até 90 caracteres |
| **Kanban** (canto superior) | Um card por incidente: Backlog → Investigando → Aguardando aprovação → Corrigindo → Concluído |
| **Painel lateral** | Pedido de aprovação, conexões (Kubernetes, Hermes, Obsidian, GitHub) e ações |
| **Log técnico** | Comandos, evidências e chamadas de ferramenta, para quem é técnico |

## O time

| Agente | Zona | Papel |
|---|---|---|
| Monitor | Agent Factory | Detecta o problema (sem IA) |
| Supervisor | Central Hub | Coordena e explica em linguagem simples |
| Investigator | Whiteboard | Encontra a causa raiz com o Hermes e a memória do time |
| Executor | Workstation | Prepara a correção e espera a sua aprovação |
| ITSM | Vault / Kanban | Registra o incidente no Hermes Brain e fecha o ciclo |

## Responder a um incidente

1. O card aparece no Kanban e o Monitor dá o alerta.
2. Acompanhe a investigação: os balões mostram o que o Hermes está lendo.
3. Quando aparecer **Aprovação humana necessária**, leia a causa, as evidências e o **comando exato**.
4. Escreva o **motivo** (obrigatório para rejeitar) e clique em **Aprovar** ou **Rejeitar**.

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

O botão **Simular Incidente** cria um incidente fictício (OOMKilled, CrashLoop ou ImagePull) sem tocar no cluster. Com
**Usar IA** desligado, não gasta cota.
