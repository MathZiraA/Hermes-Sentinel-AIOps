"""Senhas (argon2id), tokens de sessão e cifra de segredos em repouso (Fernet)."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from functools import lru_cache
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

from config import settings

log = logging.getLogger("sentinel.identity")
_hasher = PasswordHasher()  # argon2id com os parâmetros recomendados pela biblioteca
MIN_PASSWORD = 12


class WeakPassword(ValueError):
    pass


def check_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise WeakPassword(f"a senha precisa de pelo menos {MIN_PASSWORD} caracteres")
    if password.lower() == password or password.upper() == password or not any(c.isdigit() for c in password):
        raise WeakPassword("use letras maiúsculas, minúsculas e números")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored: str | None, password: str) -> bool:
    if not stored:
        _hasher.hash(password)  # gasta o mesmo tempo: não revela se o usuário existe
        return False
    try:
        return _hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_id(token: str) -> str:
    """Só o hash do token vai para o banco: um vazamento da tabela não dá sessões válidas."""
    return hashlib.sha256(token.encode()).hexdigest()


@lru_cache(maxsize=1)
def secret_key() -> bytes:
    """SENTINEL_SECRET_KEY ou, na demo, uma chave gerada em backend/data/secret.key (permissão 600)."""
    if settings.secret_key:
        return settings.secret_key.encode()
    path = Path(__file__).resolve().parent.parent / "data" / "secret.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_urlsafe(48))
        log.warning("SENTINEL_SECRET_KEY vazio: chave gerada em %s (defina a variável em produção)", path)
    return path.read_text().strip().encode()


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret_key() + b"|sentinel-fernet").digest()))


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str, ttl: int | None = None) -> str | None:
    try:
        return _fernet().decrypt(token.encode(), ttl=ttl).decode()
    except (InvalidToken, ValueError):
        return None
