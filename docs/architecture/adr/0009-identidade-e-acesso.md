# ADR 0009: Identidade e acesso: sessões no servidor, RBAC com escopo por time, 2FA e OIDC

- **Status:** aceito
- **Data:** 2026-11-18
- **Decisores:** mantenedor

## Contexto

Qualquer pessoa com acesso à porta da interface podia aprovar uma alteração no cluster. Para uso em empresa, cada
ação precisa de um autor identificado, com permissões de acordo com o papel e restritas ao que o time dela opera
([ADR 0007](0007-produto-self-hosted.md)).

## Decisão

- **Sessões no servidor**, e não JWT: um token aleatório de 256 bits vai num cookie `HttpOnly; SameSite=Lax`
  (`Secure` em produção), e o banco guarda só o SHA-256 dele. Logout, troca de senha, desativação e mudança de papel
  revogam as sessões na hora.
- **Senhas** com argon2id; política mínima de 12 caracteres, com maiúsculas, minúsculas e números; verificação em
  tempo constante, mesmo para usuários inexistentes.
- **Papéis:** Admin, Operador (reconhece, aprova, rejeita, simula), Visualizador (só leitura) e Auditor (leitura +
  auditoria). Permissões em `domain/permissions.py`, verificadas em cada rota.
- **Escopo por time:** times recebem pares (cluster, namespace), com `*` como curinga. Fora do escopo, o incidente não
  aparece (a API responde 404, sem revelar que existe). Admin e Auditor veem tudo.
- **2FA** TOTP opcional, com o segredo cifrado em repouso (Fernet com chave derivada de `SENTINEL_SECRET_KEY`).
- **SSO OIDC** com Authorization Code + PKCE, validando o `id_token` pelo JWKS do provedor (assinatura, `aud`, `iss`,
  `nonce`), com lista opcional de domínios permitidos e papel padrão para usuários novos.
- **Força bruta:** 5 falhas em 15 minutos bloqueiam por e-mail e por IP; toda falha vai para a auditoria.
- **CSRF:** além do `SameSite=Lax`, escritas vindas de uma origem fora de `CORS_ORIGINS` são recusadas (HTTP e
  WebSocket).
- **Primeira configuração:** sem usuários, a interface oferece criar o administrador (só funciona com o banco vazio),
  ou ele é criado por `SENTINEL_ADMIN_EMAIL`/`SENTINEL_ADMIN_PASSWORD`.
- **Regras de negócio:** quem propôs não decide; o motivo é obrigatório para rejeitar; o último administrador não pode
  ser rebaixado nem desativado.

## Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| JWT sem estado | Sem consulta ao banco | Revogação difícil; token exposto ao JavaScript se ficar fora de cookie |
| Só SSO | Menos código | Demonstração e instalações pequenas dependeriam de um provedor externo |
| Biblioteca pronta (fastapi-users) | Menos código | Pouco controle sobre escopo por time e auditoria |

## Consequências

- **Positivas:** cada decisão tem autor; menor privilégio também para pessoas; base para plantão e notificações.
- **Negativas:** o bloqueio de força bruta é em memória e vale por processo (várias réplicas exigirão Redis ou banco,
  Fase 7). Os eventos do WebSocket ainda não são filtrados por escopo (as animações da sala de guerra mostram todos os
  times); a API e os dados de incidente são filtrados.
