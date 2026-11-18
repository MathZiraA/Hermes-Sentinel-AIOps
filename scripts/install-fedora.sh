#!/usr/bin/env bash
# Hermes Sentinel — instalação no Fedora 44
#
# Uso:
#   scripts/install-fedora.sh              instala backend, frontend e vault
#   scripts/install-fedora.sh --with-kind  também instala kubectl + kind (cluster k8s local via podman)
#
# Seguro para rodar de novo: cada passo pula o que já está pronto.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CA_BUNDLE="/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
WITH_KIND=false
[[ "${1:-}" == "--with-kind" ]] && WITH_KIND=true

c_ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
c_warn() { printf '\033[33m!\033[0m %s\n' "$*"; }
c_err()  { printf '\033[31m✗\033[0m %s\n' "$*" >&2; }
step()   { printf '\n\033[1m→ %s\033[0m\n' "$*"; }

need_dnf=()

# ---------------------------------------------------------------- 1. dependências
step "Verificando dependências"
for bin in python3 git; do
  if command -v "$bin" >/dev/null; then c_ok "$bin: $($bin --version 2>&1 | head -1)"; else need_dnf+=("$bin"); fi
done
python3 -m pip --version >/dev/null 2>&1 && c_ok "pip ok" || need_dnf+=(python3-pip)
python3 -c 'import venv' 2>/dev/null || need_dnf+=(python3-virtualenv)

if command -v bun >/dev/null; then
  JS_PM=bun; c_ok "bun: $(bun --version)"
elif command -v npm >/dev/null; then
  JS_PM=npm; c_ok "npm: $(npm --version) (bun não encontrado; usando npm)"
else
  need_dnf+=(nodejs npm); JS_PM=npm
fi

if command -v kubectl >/dev/null; then
  c_ok "kubectl: $(kubectl version --client 2>/dev/null | head -1)"
else
  c_warn "kubectl não encontrado (o modo simulação funciona sem ele; use --with-kind para instalar)"
fi

if ((${#need_dnf[@]})); then
  step "Instalando pacotes do sistema: ${need_dnf[*]}"
  sudo dnf install -y "${need_dnf[@]}"
fi

# ---------------------------------------------------------------- 2. certificados
step "Certificados (HTTPS do Hermes Gateway no VPS)"
if [[ -f "$CA_BUNDLE" ]]; then
  c_ok "bundle do Fedora: $CA_BUNDLE"
  if grep -q "Caddy Local Authority" "$CA_BUNDLE" 2>/dev/null || trust list 2>/dev/null | grep -q "Caddy Local Authority"; then
    c_ok "CA do servidor Hermes está confiável no sistema"
  else
    c_warn "CA do servidor Hermes NÃO está no bundle. Instale com:"
    echo "    sudo cp hermes-servidor-ca.crt /etc/pki/ca-trust/source/anchors/hermes-servidor.crt && sudo update-ca-trust"
  fi
else
  c_err "Bundle $CA_BUNDLE não existe (pacote ca-certificates)"; exit 1
fi

# ---------------------------------------------------------------- 3. backend Python
step "Backend Python (backend/.venv)"
if [[ ! -x "$ROOT/backend/.venv/bin/python" ]]; then
  python3 -m venv "$ROOT/backend/.venv"
fi
# pip usa o bundle do Fedora (inclui a CA do Hermes)
export SSL_CERT_FILE="$CA_BUNDLE" REQUESTS_CA_BUNDLE="$CA_BUNDLE" PIP_CERT="$CA_BUNDLE"
"$ROOT/backend/.venv/bin/python" -m pip install -q --upgrade pip
"$ROOT/backend/.venv/bin/python" -m pip install -q -r "$ROOT/backend/requirements-dev.txt"
c_ok "dependências Python instaladas"

# Faz o Python do venv confiar no bundle do Fedora em qualquer execução (sitecustomize)
SITE_DIR="$("$ROOT/backend/.venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
cat > "$SITE_DIR/sitecustomize.py" <<PY
import os
os.environ.setdefault("SSL_CERT_FILE", "$CA_BUNDLE")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "$CA_BUNDLE")
PY
c_ok "venv configurado para usar $CA_BUNDLE"

# ---------------------------------------------------------------- 4. frontend
step "Frontend ($JS_PM install)"
if [[ "$JS_PM" == "bun" ]]; then
  (cd "$ROOT" && bun install)
else
  # --legacy-peer-deps: o npm 10 quebra ("edgesOut") com o bloco "overrides" do package.json
  (cd "$ROOT" && npm install --no-audit --no-fund --legacy-peer-deps)
  # peer dependency dos testes que o bun instala sozinho e o npm --legacy-peer-deps não
  (cd "$ROOT" && npm install --no-save --no-audit --no-fund --legacy-peer-deps @testing-library/dom)
fi
c_ok "dependências do frontend instaladas"

# ---------------------------------------------------------------- 5. .env + vault
step "Configuração e Obsidian Vault"
if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  chmod 600 "$ROOT/.env"
  c_warn ".env criado a partir do .env.example — preencha HERMES_GATEWAY_TOKEN"
else
  c_ok ".env já existe (não foi alterado)"
fi
mkdir -p "$ROOT/obsidian-vault"
# O backend monta o resto da estrutura do Hermes Brain (pastas, hubs, equipe) na primeira subida.
c_ok "Hermes Brain em $ROOT/obsidian-vault ($(find "$ROOT/obsidian-vault" -name 'Runbook - *.md' | wc -l) runbooks)"

# ---------------------------------------------------------------- 6. kubectl + kind (opcional)
if $WITH_KIND; then
  step "kubectl + kind (cluster local com podman)"
  if ! command -v kubectl >/dev/null; then
    sudo dnf install -y kubernetes-client
  fi
  if ! command -v kind >/dev/null; then
    KIND_VERSION="v0.33.0"
    mkdir -p "$HOME/.local/bin"
    curl -fsSLo "$HOME/.local/bin/kind" "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-amd64"
    chmod +x "$HOME/.local/bin/kind"
    c_ok "kind ${KIND_VERSION} em ~/.local/bin/kind"
  fi
  # kind rootless com podman precisa que o systemd delegue os controladores de cgroup
  if [[ ! -f /etc/systemd/system/user@.service.d/delegate.conf ]]; then
    sudo mkdir -p /etc/systemd/system/user@.service.d
    printf '[Service]\nDelegate=yes\n' | sudo tee /etc/systemd/system/user@.service.d/delegate.conf >/dev/null
    sudo systemctl daemon-reload
    c_warn "delegação de cgroups ativada — faça logout/login (ou reinicie) antes do primeiro 'kind create cluster'"
  fi
  c_ok "pronto. Suba um cluster de teste com: kind create cluster --name stockflow"
fi

printf '\n\033[1;32mInstalação concluída.\033[0m Rode `make dev` para subir backend (8000) e frontend (3000).\n'
