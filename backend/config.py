"""Configuração do Hermes Sentinel, lida do .env na raiz do repositório."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent

load_dotenv(ROOT_DIR / ".env", override=False)

DEFAULT_CA_BUNDLE = "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"


def _path(value: str, base: Path = ROOT_DIR) -> Path:
    p = Path(os.path.expandvars(os.path.expanduser(value)))
    return p if p.is_absolute() else (base / p).resolve()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def _role_tokens(raw: str) -> dict[str, str]:
    """ "papel:token,papel:token" → {token: papel}."""
    out: dict[str, str] = {}
    for item in raw.split(","):
        role, _, tok = item.strip().partition(":")
        if role.strip() and tok.strip():
            out[tok.strip()] = role.strip().lower()
    return out


@dataclass(frozen=True)
class Settings:
    hermes_gateway_url: str = field(
        default_factory=lambda: os.getenv("HERMES_GATEWAY_URL", "https://hermes.example.internal:8443").rstrip("/")
    )
    hermes_gateway_token: str = field(default_factory=lambda: os.getenv("HERMES_GATEWAY_TOKEN", "").strip())
    hermes_model: str = field(default_factory=lambda: os.getenv("HERMES_MODEL", "hermes-agent"))
    hermes_mode: str = field(default_factory=lambda: os.getenv("HERMES_MODE", "gateway").strip().lower())
    hermes_timeout: float = field(default_factory=lambda: float(os.getenv("HERMES_TIMEOUT_SECONDS", "90") or 90))
    hermes_local_cli_path: Path = field(default_factory=lambda: _path(os.getenv("HERMES_LOCAL_CLI_PATH", "~/.hermes")))
    # Intervalo mínimo entre duas chamadas de IA (protege a quota grátis do Gemini Flash)
    ai_min_interval: float = field(default_factory=lambda: float(os.getenv("AI_MIN_INTERVAL_SECONDS", "8") or 8))

    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_fallback_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
    )

    ssl_cert_file: str = field(default_factory=lambda: os.getenv("SSL_CERT_FILE", DEFAULT_CA_BUNDLE))

    kubeconfig_path: Path = field(default_factory=lambda: _path(os.getenv("KUBECONFIG_PATH", "~/.kube/config")))
    k8s_namespaces: tuple[str, ...] = field(
        default_factory=lambda: tuple(n.strip() for n in os.getenv("K8S_NAMESPACES", "").split(",") if n.strip())
    )
    k8s_log_tail_lines: int = field(default_factory=lambda: _int("K8S_LOG_TAIL_LINES", 80))

    # Servidor MCP que o Hermes (VPS) usa pelo túnel SSH reverso. Só escuta em 127.0.0.1.
    mcp_port: int = field(default_factory=lambda: _int("SENTINEL_MCP_PORT", 8765))
    mcp_token: str = field(default_factory=lambda: os.getenv("SENTINEL_MCP_TOKEN", "").strip())
    # "monitor:tok,investigator:tok,..." — um token por bot (profile do Hermes); cada papel só usa as suas ferramentas
    mcp_role_tokens: dict[str, str] = field(
        default_factory=lambda: _role_tokens(os.getenv("SENTINEL_MCP_ROLE_TOKENS", ""))
    )
    # Investigação agêntica: o Hermes chama as ferramentas MCP (mais lento que 1 chamada simples)
    hermes_agent_timeout: float = field(
        default_factory=lambda: float(os.getenv("HERMES_AGENT_TIMEOUT_SECONDS", "240") or 240)
    )

    obsidian_vault_path: Path = field(
        default_factory=lambda: _path(os.getenv("OBSIDIAN_VAULT_PATH", "./obsidian-vault"))
    )

    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", "").strip())
    github_repo: str = field(default_factory=lambda: os.getenv("GITHUB_REPO", "MathZiraA/Hermes-Sentinel-AIOps"))

    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://localhost:5173,http://localhost:8080,"
                "http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8080",
            ).split(",")
            if o.strip()
        )
    )

    @property
    def runbooks_dir(self) -> Path:
        return self.obsidian_vault_path / "06 - Runbooks"

    @property
    def postmortems_dir(self) -> Path:
        return self.obsidian_vault_path / "04 - Incidentes"

    @property
    def ca_bundle(self) -> str | bool:
        """Bundle de CAs para HTTPS. Cai para a verificação padrão se o arquivo não existir."""
        return self.ssl_cert_file if Path(self.ssl_cert_file).is_file() else True


settings = Settings()
