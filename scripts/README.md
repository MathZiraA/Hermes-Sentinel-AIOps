# Scripts

Scripts de instalação e desenvolvimento. Normalmente são chamados pelo `Makefile` da raiz.

| Script              | Comando           | O que faz                                                          |
| ------------------- | ----------------- | ------------------------------------------------------------------ |
| `install-fedora.sh` | `make setup`      | instala o backend (`backend/.venv`), o frontend e cria o `.env`    |
|                     | `make setup-kind` | o mesmo, mais `kubectl` e `kind` para um cluster local             |
| `start.sh`          | `make dev`        | sobe a API (:8000) e a interface (:3000); Ctrl+C encerra os dois   |

O CI roda `shellcheck` em todos os scripts desta pasta.
