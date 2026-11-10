"""Criptografia simétrica de segredos em repouso (A13 da auditoria).

Alguns segredos precisam viver no banco (ex.: a chave privada VAPID, cuja
estabilidade é obrigatória para o Web Push). Guardá-los em texto claro expõe
todo o valor a um dump, backup ou leitura indevida da tabela ``app_settings``.

Formato do valor cifrado::

    enc:v1:<base64url(nonce || ciphertext+tag)>

- AES-256-GCM: confidencialidade e detecção de adulteração;
- a chave é derivada do ``JWT_SECRET_KEY`` (SHA-256), então o segredo nunca é
  gravado junto do dado;
- prefixo versionado permite trocar o algoritmo depois;
- valores sem o prefixo são tratados como legado em texto claro (a leitura
  continua funcionando e o chamador pode migrá-los).
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import settings

PREFIX = "enc:v1:"
_NONCE_BYTES = 12


class SecretBoxError(ValueError):
    """Valor cifrado inválido ou chave de criptografia diferente."""


def _key() -> bytes:
    return hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()


def is_encrypted(value: str) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt(plaintext: str) -> str:
    """Cifra ``plaintext`` com AES-256-GCM e devolve o valor versionado."""
    nonce = os.urandom(_NONCE_BYTES)
    sealed = AESGCM(_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return PREFIX + base64.urlsafe_b64encode(nonce + sealed).decode("ascii")


def decrypt(value: str) -> str:
    """Decifra um valor; texto claro legado é devolvido sem alteração."""
    if not is_encrypted(value):
        return value
    try:
        raw = base64.urlsafe_b64decode(value[len(PREFIX):].encode("ascii"))
        nonce, sealed = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        if len(nonce) != _NONCE_BYTES or not sealed:
            raise ValueError("payload truncado")
        return AESGCM(_key()).decrypt(nonce, sealed, None).decode("utf-8")
    except (InvalidTag, ValueError, UnicodeDecodeError) as exc:
        raise SecretBoxError(
            "Não foi possível decifrar o valor (JWT_SECRET_KEY mudou?)"
        ) from exc
