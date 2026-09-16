"""Gera um par de chaves VAPID (P-256) para Web Push e imprime em base64url.

Uso: python gen_vapid_keys.py
Cole os valores em VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY no .env do backend.
"""
import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())

    private_der = private_key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    # Formato "raw" (ponto não comprimido, 65 bytes) — é o que o navegador
    # espera em applicationServerKey e o que pywebpush aceita como public key.
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )

    print("VAPID_PRIVATE_KEY=" + b64url(private_der))
    print("VAPID_PUBLIC_KEY=" + b64url(public_raw))


if __name__ == "__main__":
    main()