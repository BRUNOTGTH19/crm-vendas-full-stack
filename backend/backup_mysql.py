"""Backup lógico do MySQL (P0 da auditoria).

O reset de dados e o próprio banco não tinham rotina de backup. Este script
gera um dump consistente e comprimido, pensado para rodar no shell do provedor
ou em um cron job externo:

    python backup_mysql.py --output-dir /var/backups/crm --keep 14

Decisões de segurança:

- ``--single-transaction``: dump consistente sem travar as tabelas InnoDB;
- a senha não aparece em ``argv`` (visível no ``ps``) nem em variável de
  ambiente: vai em um arquivo temporário com permissão restrita, apagado ao fim;
- o resultado é validado (cabeçalho do ``mysqldump``) antes de ser aceito;
- dumps mais antigos que ``--keep`` são removidos, mas um dump inválido nunca
  substitui um backup bom.

Requer o binário ``mysqldump`` disponível no servidor.
"""
from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import URL, make_url

from config import settings

DUMP_PREFIX = "crm-"
DUMP_SUFFIX = ".sql.gz"
MYSQLDUMP_HEADER = b"-- MySQL dump"
REQUIRED_SCHEMES = ("mysql", "mysql+pymysql", "mysql+mysqldb")


class BackupError(RuntimeError):
    """Falha ao gerar ou validar o backup."""


def dump_filename(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"{DUMP_PREFIX}{now:%Y%m%d-%H%M%S}{DUMP_SUFFIX}"


def client_config(url: URL) -> str:
    """Conteúdo do ``--defaults-extra-file`` (senha fora de argv/env)."""
    lines = ["[client]"]
    if url.host:
        lines.append(f"host={url.host}")
    if url.port:
        lines.append(f"port={url.port}")
    if url.username:
        lines.append(f"user={url.username}")
    if url.password:
        lines.append(f"password={url.password}")
    lines.append("default-character-set=utf8mb4")
    return "\n".join(lines) + "\n"


def dump_arguments(config_path: str, database: str) -> list[str]:
    """Argumentos do ``mysqldump`` com o arquivo de credenciais."""
    return [
        "mysqldump",
        f"--defaults-extra-file={config_path}",
        "--single-transaction",
        "--quick",
        "--routines",
        "--triggers",
        "--no-tablespaces",
        "--default-character-set=utf8mb4",
        database,
    ]


def validate_dump(path: Path) -> None:
    """Confere se o gzip abre e começa com o cabeçalho do mysqldump."""
    try:
        with gzip.open(path, "rb") as handle:
            head = handle.read(128)
    except OSError as exc:
        raise BackupError(f"Arquivo de backup inválido: {exc}") from exc
    if not head.startswith(MYSQLDUMP_HEADER):
        raise BackupError("O dump não contém o cabeçalho esperado do mysqldump.")


def prune_backups(output_dir: Path, keep: int) -> list[Path]:
    """Remove os dumps mais antigos, mantendo os ``keep`` mais recentes."""
    if keep < 1:
        raise ValueError("--keep deve ser pelo menos 1.")
    dumps = sorted(
        output_dir.glob(f"{DUMP_PREFIX}*{DUMP_SUFFIX}"),
        # O nome é cronológico; a data de modificação desempata cópias movidas.
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    removed = dumps[keep:]
    for path in removed:
        path.unlink(missing_ok=True)
    return removed


def create_backup(
    output_dir: str | Path,
    *,
    keep: int = 14,
    database_url: str | None = None,
    dump_cmd: list[str] | None = None,
    now: datetime | None = None,
) -> Path:
    """Gera ``crm-YYYYmmdd-HHMMSS.sql.gz`` e aplica a retenção.

    ``dump_cmd`` existe para testes; em produção o comando é montado a partir
    de ``DATABASE_URL`` e do ``mysqldump`` do sistema.
    """
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / dump_filename(now)
    temporary = target.with_suffix(target.suffix + ".part")

    url = make_url(database_url or settings.database_url)
    config_path: str | None = None
    try:
        if dump_cmd is None:
            if url.get_backend_name() not in ("mysql",):
                raise BackupError(
                    "DATABASE_URL não aponta para MySQL; mysqldump não se aplica."
                )
            if not shutil.which("mysqldump"):
                raise BackupError(
                    "mysqldump não encontrado no PATH. Instale o cliente do MySQL."
                )
            with tempfile.NamedTemporaryFile(
                "w", suffix=".cnf", delete=False, encoding="utf-8"
            ) as config_file:
                config_file.write(client_config(url))
                config_path = config_file.name
            os.chmod(config_path, 0o600)
            dump_cmd = dump_arguments(config_path, url.database or "")

        completed = subprocess.run(
            dump_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            message = completed.stderr.decode("utf-8", "replace").strip()
            raise BackupError(
                f"mysqldump falhou (código {completed.returncode}): {message[:500]}"
            )

        with gzip.open(temporary, "wb") as output:
            output.write(completed.stdout)
        validate_dump(temporary)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    finally:
        if config_path:
            Path(config_path).unlink(missing_ok=True)

    prune_backups(target_dir, keep)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup lógico do MySQL do CRM.")
    parser.add_argument(
        "--output-dir",
        default=os.getenv("BACKUP_DIR", "backups"),
        help="Diretório dos dumps (padrão: ./backups ou BACKUP_DIR).",
    )
    parser.add_argument(
        "--keep", type=int, default=14, help="Quantos dumps manter (padrão: 14)."
    )
    args = parser.parse_args(argv)

    try:
        path = create_backup(args.output_dir, keep=args.keep)
    except BackupError as exc:
        print(f"Falha no backup: {exc}", file=sys.stderr)
        return 1

    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Backup criado: {path} ({size_mb:.1f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
