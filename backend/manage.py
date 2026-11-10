"""Operações de manutenção executadas no servidor (sem HTTP).

Recuperação de acesso e rotação de segredos, sem depender da redefinição
"simples" por e-mail (``POST /auth/reset-password``), que vem **desligada** por
padrão por ser um vetor de tomada de conta (A1 da auditoria).

    python manage.py set-password --email dono@crm.com
    python manage.py promote-admin --email dono@crm.com
    python manage.py revoke-sessions --email dono@crm.com
    python manage.py rotate-admin-code
    python manage.py expire-admin-code

A senha é lida do terminal (não aparece no histórico do shell nem no ``ps``).
Toda troca de senha incrementa ``token_version`` e apaga a sessão informativa
do Redis, então qualquer token antigo deixa de valer imediatamente.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from database import SessionLocal
from models.audit_log import AuditLog
from models.user import User, UserRole
from services.auth_service import (
    delete_session,
    expire_admin_setup_code,
    hash_password,
    rotate_admin_setup_code,
)

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


def _find_user(db, email: str) -> User | None:
    return db.query(User).filter(User.email == (email or "").strip().lower()).first()


def _audit(db, user_id: int | None, action: str, detail: str) -> None:
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))
    db.commit()


def set_password(email: str) -> int:
    """Troca a senha da conta ``email``. Devolve o código de saída do processo."""
    normalized = (email or "").strip().lower()
    with SessionLocal() as db:
        user = _find_user(db, normalized)
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


def promote_admin(email: str) -> int:
    """Promove uma conta existente a administrador (recuperação explícita)."""
    normalized = (email or "").strip().lower()
    with SessionLocal() as db:
        user = _find_user(db, normalized)
        if user is None:
            print(f"Conta não encontrada: {normalized}", file=sys.stderr)
            return 1
        if user.role == UserRole.admin:
            print(f"{normalized} já é administrador.")
            return 0
        user.role = UserRole.admin
        _audit(db, user.id, "admin_promoted_cli", "operador via manage.py")
        user_id = user.id

    print(f"{normalized} promovido a administrador (user_id={user_id}).")
    return 0


def revoke_sessions(email: str) -> int:
    """Invalida todos os tokens da conta (incrementa ``token_version``)."""
    normalized = (email or "").strip().lower()
    with SessionLocal() as db:
        user = _find_user(db, normalized)
        if user is None:
            print(f"Conta não encontrada: {normalized}", file=sys.stderr)
            return 1
        user.token_version = int(user.token_version or 0) + 1
        _audit(db, user.id, "sessions_revoked_cli", "operador via manage.py")
        user_id = user.id

    try:
        delete_session(user_id)
    except Exception:  # pragma: no cover - Redis indisponível não bloqueia
        pass

    print(f"Sessões de {normalized} revogadas (user_id={user_id}).")
    return 0


def rotate_admin_code() -> int:
    """Gera um novo código de ativação e mostra o texto claro uma única vez."""
    with SessionLocal() as db:
        try:
            code = rotate_admin_setup_code(db)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        _audit(db, None, "admin_code_rotated", "operador via manage.py")

    print("Novo código de ativação (guarde-o; ele não será exibido de novo):")
    print(f"  {code}")
    return 0


def expire_admin_code() -> int:
    """Encerra a ativação por código gerado."""
    with SessionLocal() as db:
        expire_admin_setup_code(db)
        _audit(db, None, "admin_code_expired", "operador via manage.py")
    print("Ativação por código gerado encerrada.")
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

    promote = sub.add_parser(
        "promote-admin", help="Promove uma conta existente a administrador."
    )
    promote.add_argument("--email", required=True, help="E-mail da conta.")

    revoke = sub.add_parser(
        "revoke-sessions", help="Invalida todos os tokens da conta."
    )
    revoke.add_argument("--email", required=True, help="E-mail da conta.")

    sub.add_parser(
        "rotate-admin-code", help="Invalida o código atual e gera um novo."
    )
    sub.add_parser(
        "expire-admin-code", help="Encerra a ativação por código gerado."
    )

    args = parser.parse_args(argv)
    if args.command == "set-password":
        return set_password(args.email)
    if args.command == "promote-admin":
        return promote_admin(args.email)
    if args.command == "revoke-sessions":
        return revoke_sessions(args.email)
    if args.command == "rotate-admin-code":
        return rotate_admin_code()
    if args.command == "expire-admin-code":
        return expire_admin_code()
    parser.error("comando desconhecido")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
