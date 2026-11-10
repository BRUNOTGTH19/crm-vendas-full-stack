"""Restauração e verificação de um backup lógico do MySQL (P0 da auditoria).

Complementa ``backup_mysql.py``: aplica o ``.sql.gz`` em um banco descartável
para provar que o backup realmente volta. Um backup que nunca foi restaurado é
só uma esperança.

    python restore_mysql.py \\
        --dump backups/crm-20261110-030000.sql.gz \\
        --database crm_restore_check --create --compare --drop

Decisões de segurança:

- a senha só existe no arquivo temporário ``--defaults-extra-file`` com
  permissão restrita, nunca em ``argv`` nem em variável de ambiente;
- o destino nunca pode ser o banco de origem (produção): restaurar por cima do
  banco real é sempre recusado;
- ``--drop`` só é aceito junto de ``--create``, então o script jamais apaga um
  banco que já existia antes da execução;
- o dump é validado (gzip + cabeçalho do ``mysqldump``) antes de tocar no banco;
- ``--compare`` falha se o banco restaurado tiver menos tabelas que o original.

Requer o binário ``mysql`` no PATH.
"""
from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from backup_mysql import BackupError, client_config, validate_dump
from config import settings

DATABASE_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")


class RestoreError(RuntimeError):
    """Falha ao restaurar ou validar a restauração."""


@dataclass(frozen=True)
class RestoreResult:
    """Resumo de uma restauração verificada."""

    database: str
    tables: int
    source_tables: int | None = None
    dropped: bool = False


def validate_database_name(name: str) -> str:
    """Aceita apenas nomes simples, sem aspas nem ``;`` (vão para o SQL)."""
    if not DATABASE_NAME_RE.match(name or ""):
        raise RestoreError(
            f"Nome de banco inválido: {name!r}. Use apenas letras, números e _."
        )
    return name


def ensure_not_source(database: str, source_url: str | URL) -> None:
    """Recusa restaurar por cima do banco de origem (produção)."""
    source = make_url(source_url) if isinstance(source_url, str) else source_url
    if (source.database or "") == database:
        raise RestoreError(
            "O banco de destino é o mesmo da DATABASE_URL; "
            "restaure em um banco separado e valide antes de trocar."
        )


def restore_arguments(config_path: str, database: str) -> list[str]:
    """Argumentos do cliente ``mysql``; a senha fica só no arquivo de credenciais."""
    return [
        "mysql",
        f"--defaults-extra-file={config_path}",
        "--default-character-set=utf8mb4",
        database,
    ]


def _run_sql(url: URL, sql: str, database: str | None = None) -> None:
    engine = create_engine(url.set(database=database), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text(sql))
    finally:
        engine.dispose()


def create_database(url: URL, database: str) -> None:
    """Cria o banco destino em ``utf8mb4`` (idempotente)."""
    validate_database_name(database)
    _run_sql(
        url,
        f"CREATE DATABASE IF NOT EXISTS `{database}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
    )


def drop_database(url: URL, database: str) -> None:
    """Apaga o banco destino (usado só quando o próprio script o criou)."""
    validate_database_name(database)
    _run_sql(url, f"DROP DATABASE IF EXISTS `{database}`")


def count_tables(url: URL, database: str) -> int:
    """Quantas tabelas existem no banco (para comparar origem e restauração)."""
    engine = create_engine(url.set(database=database), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            total = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = :database AND table_type = 'BASE TABLE'"
                ),
                {"database": database},
            ).scalar_one()
    finally:
        engine.dispose()
    return int(total)


def _pipe_dump(path: Path, command: list[str]) -> None:
    """Descomprime o dump direto no ``stdin`` do cliente ``mysql``."""
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None and process.stderr is not None
    try:
        with gzip.open(path, "rb") as source:
            shutil.copyfileobj(source, process.stdin, length=64 * 1024)
        process.stdin.close()
    except BrokenPipeError:
        # O mysql saiu antes do fim; o código de saída e o stderr explicam.
        pass
    completed_stderr = process.stderr.read()
    process.stderr.close()
    if process.stdout is not None:
        process.stdout.close()
    code = process.wait()
    if code != 0:
        message = completed_stderr.decode("utf-8", "replace").strip()
        raise RestoreError(f"mysql falhou (código {code}): {message[:500]}")


def restore_dump(
    dump_path: str | Path,
    database: str,
    *,
    database_url: str | None = None,
    create: bool = False,
    compare: bool = False,
    drop_after: bool = False,
    mysql_cmd: list[str] | None = None,
    count_fn=None,
) -> RestoreResult:
    """Restaura ``dump_path`` em ``database`` e devolve o resumo.

    ``mysql_cmd`` e ``count_fn`` existem para os testes: em produção o comando
    vem de ``DATABASE_URL`` e a contagem vai ao ``information_schema``.
    """
    if drop_after and not create:
        raise RestoreError("--drop exige --create: só apagamos o banco criado aqui.")
    validate_database_name(database)

    dump = Path(dump_path)
    if not dump.is_file():
        raise RestoreError(f"Backup não encontrado: {dump}")

    url = make_url(database_url or settings.database_url)
    ensure_not_source(database, url)
    if url.get_backend_name() != "mysql":
        raise RestoreError("DATABASE_URL não aponta para MySQL.")

    try:
        validate_dump(dump)
    except BackupError as exc:
        raise RestoreError(str(exc)) from exc

    config_path: str | None = None
    created = False
    dropped = False
    try:
        if mysql_cmd is None:
            if not shutil.which("mysql"):
                raise RestoreError(
                    "mysql não encontrado no PATH. Instale o cliente do MySQL."
                )
            with tempfile.NamedTemporaryFile(
                "w", suffix=".cnf", delete=False, encoding="utf-8"
            ) as config_file:
                config_file.write(client_config(url))
                config_path = config_file.name
            os.chmod(config_path, 0o600)
            mysql_cmd = restore_arguments(config_path, database)

        if create:
            create_database(url, database)
            created = True

        _pipe_dump(dump, mysql_cmd)

        tables = (
            count_fn()
            if count_fn
            else count_tables(url, database)
        )
        source_tables = count_tables(url, url.database or "") if compare else None
        if source_tables is not None and tables < source_tables:
            raise RestoreError(
                "Restauração incompleta: "
                f"{tables} tabelas no destino contra {source_tables} na origem."
            )
    finally:
        if config_path:
            Path(config_path).unlink(missing_ok=True)
        if created and drop_after:
            drop_database(url, database)
            dropped = True

    return RestoreResult(
        database=database,
        tables=tables,
        source_tables=source_tables,
        dropped=dropped,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restaura um dump do CRM em um banco descartável e valida."
    )
    parser.add_argument("--dump", required=True, help="Arquivo .sql.gz do backup.")
    parser.add_argument("--database", required=True, help="Banco de destino.")
    parser.add_argument(
        "--create", action="store_true", help="Cria o banco de destino se faltar."
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Falha se o destino tiver menos tabelas que a origem.",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        dest="drop_after",
        help="Apaga o banco no fim (exige --create).",
    )
    args = parser.parse_args(argv)

    try:
        result = restore_dump(
            args.dump,
            args.database,
            create=args.create,
            compare=args.compare,
            drop_after=args.drop_after,
        )
    except RestoreError as exc:
        print(f"Falha na restauração: {exc}", file=sys.stderr)
        return 1

    origin = (
        f", origem com {result.source_tables} tabelas"
        if result.source_tables is not None
        else ""
    )
    suffix = " (banco de teste removido)" if result.dropped else ""
    print(
        f"Restauração verificada: {result.database} com {result.tables} tabelas"
        f"{origin}{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
