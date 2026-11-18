#!/usr/bin/env bash
# Hermes Sentinel — sobe backend (FastAPI :8000) e frontend (Vite :3000). Ctrl+C encerra os dois.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ---------------------------------------------------------------- .env
if [[ ! -f .env ]]; then
  echo "✗ .env não encontrado. Rode `make setup` primeiro." >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
export SSL_CERT_FILE="${SSL_CERT_FILE:-/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem}"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"

if [[ ! -x backend/.venv/bin/uvicorn ]]; then
  echo "✗ backend/.venv não existe. Rode `make setup` primeiro." >&2
  exit 1
fi
[[ -z "${HERMES_GATEWAY_TOKEN:-}" ]] && echo "! HERMES_GATEWAY_TOKEN vazio: o Investigator usará o RCA demonstrativo (sem IA)."

# ---------------------------------------------------------------- kubectl / cluster
KCFG="${KUBECONFIG_PATH:-$HOME/.kube/config}"
KCFG="${KCFG/#\~/$HOME}"
if command -v kubectl >/dev/null && [[ -f "$KCFG" ]]; then
  if kubectl --kubeconfig "$KCFG" cluster-info --request-timeout=4s >/dev/null 2>&1; then
    echo "✓ cluster k8s: $(kubectl --kubeconfig "$KCFG" config current-context)"
  else
    echo "! kubeconfig existe, mas o cluster não respondeu. O Monitor tenta reconectar sozinho."
  fi
else
  echo "! sem kubectl/kubeconfig: o Monitor fica em espera e o modo simulação funciona normalmente."
fi

port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
for p in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if port_busy "$p"; then
    echo "✗ porta $p já está em uso. Encerre o processo ou mude BACKEND_PORT/FRONTEND_PORT no .env." >&2
    exit 1
  fi
done

# ---------------------------------------------------------------- processos
pids=()
cleanup() {
  trap - INT TERM EXIT
  echo
  echo "→ encerrando Hermes Sentinel…"
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  echo "✓ tudo encerrado"
}
trap cleanup INT TERM EXIT

echo "→ backend  http://localhost:$BACKEND_PORT  (docs: /docs · ws: /ws/telemetry)"
(cd backend && exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port "$BACKEND_PORT") &
pids+=($!)

echo "→ frontend http://localhost:$FRONTEND_PORT"
if command -v bun >/dev/null; then
  bun run dev -- --port "$FRONTEND_PORT" --host 127.0.0.1 &
else
  npm run dev -- --port "$FRONTEND_PORT" --host 127.0.0.1 &
fi
pids+=($!)

# Se qualquer um cair, derruba o outro.
wait -n "${pids[@]}"
echo "! um dos processos terminou; encerrando o outro."
