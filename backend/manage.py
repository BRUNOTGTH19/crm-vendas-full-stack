"""Operações de manutenção executadas no servidor (sem HTTP).

Uso principal: recuperar o acesso de uma conta sem depender da redefinição
"simples" por e-mail (``POST /auth/reset-password``), que vem **desligada**
por padrão por ser um vetor de tomada de conta (A1 da auditoria).

    python manage.py set-password --email dono@crm.com

A senha é lida do terminal (não aparece no histórico do shell nem no
``ps``). A troca incrementa ``token_version`` e apaga a sessão informativa do
Redis, então qualquer token antigo deixa de valer imediatamente.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from database import SessionLocal
from models.audit_log import AuditLog
from models.user import User
from services.auth_service import delete_session, hash_password

MIN_PASSWORD_LENGTH = 8
# bcrypt ignora silenciosamente o que passa de 72 bytes.
MAX_PASSWORD_LENGTH = 72


def _read_password() -> str:
    password = getpass.getpass("Nova senha: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"Senha muito curta: mínimo de {MIN_PASSWORD_LENGTH} caracteres."
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        raise SystemExit(
            f"Senha muito longa: máximo de {MAX_PASSWORD_LENGTH} bytes (UTF-8)."
        )
    if password != getpass.getpass("Confirme a nova senha: "):
        raise SystemExit("As senhas não coincidem.")
    return password


def set_password(email: str) -> int:
    """Troca a senha da conta ``email``. Devolve o código de saída do processo."""
    normalized = (email or "").strip().lower()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == normalized).first()
        if user is None:
            print(f"Conta não encontrada: {normalized}", file=sys.stderr)
            return 1

        password = _read_password()
        user.password_hash = hash_password(password)
        user.token_version = int(user.token_version or 0) + 1
        db.add(
            AuditLog(
                user_id=user.id,
                action="password_set_cli",
                detail="operador via manage.py",
            )
        )
        db.commit()
        user_id = user.id

    # Fora da transação: o Redis é best-effort e não deve desfazer a troca.
    try:
        delete_session(user_id)
    except Exception:  # pragma: no cover - Redis indisponível não bloqueia
        pass

    print(f"Senha atualizada para {normalized} (user_id={user_id}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operações administrativas do CRM (executar no servidor)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    set_pwd = sub.add_parser(
        "set-password", help="Define uma nova senha para uma conta existente."
    )
    set_pwd.add_argument("--email", required=True, help="E-mail da conta.")

    args = parser.parse_args(argv)
    if args.command == "set-password":
        return set_password(args.email)
    parser.error("comando desconhecido")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
